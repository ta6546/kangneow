#!/usr/bin/env python3
"""강고양이 매매법 기준으로 바이낸스 USDⓈ-M 선물 종목을 걸러주는 스크리너.

표준 라이브러리만 씁니다(Python 3.9+). 매수·매도 추천이 아니라, 관심 목록 후보를 뽑는 도구예요.

사용 예:
  python tools/screener.py                    # 바이낸스 실시간 API (한국 등에서)
  python tools/screener.py --vol 350          # 거래대금 기준 350M
  python tools/screener.py --source archive   # data.binance.vision (하루 늦음, API가 막힌 곳에서)
  python tools/screener.py --source archive --asof 2026-03-17   # 과거 날짜로 검증
"""
import argparse, calendar, csv, re, datetime as dt, io, json, os, statistics, sys, time, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "kangneow-screener/1.0"}
FAPI = "https://fapi.binance.com"
ARCH = "https://data.binance.vision/data/futures/um"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
SKIP = {"BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "USDC", "FDUSD",
        "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT"}  # 대형 코인, 스테이블, 원자재


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None
            if e.code == 451:
                sys.exit("바이낸스 API가 이 지역에서 막혀 있어요(451). --source archive 로 실행하세요.")
            time.sleep(2 * (i + 1))
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def base_asset(sym):
    b = sym[:-4]
    for p in ("1000000", "1000"):
        if b.startswith(p) and len(b) > len(p):
            return b[len(p):]
    return b


# ---------- 국내 상장 목록 ----------
def korean_listed():
    out = set()
    raw = get("https://api.upbit.com/v1/market/all")
    if raw:
        for m in json.loads(raw):  # KRW-, BTC-, USDT- 마켓 전부
            out.add(m["market"].split("-")[1])
    for q in ("ALL_KRW", "ALL_BTC"):
        raw = get(f"https://api.bithumb.com/public/ticker/{q}")
        if raw:
            out |= {k for k in json.loads(raw).get("data", {}) if k != "date"}
    if not out:
        print("경고: 업비트·빗썸 목록을 못 받아서 국내 상장 제외를 건너뜁니다.", file=sys.stderr)
    return out


# ---------- 데이터: 실시간 API ----------
def api_symbols():
    info = json.loads(get(f"{FAPI}/fapi/v1/exchangeInfo"))
    return [s["symbol"] for s in info["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING"
            and s.get("underlyingType", "COIN") == "COIN"]  # 주식·원자재 선물 제외


def api_klines(sym, interval, limit):
    raw = get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval={interval}&limit={limit}")
    if not raw:
        return []
    return [(int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])) for k in json.loads(raw)]


# ---------- 데이터: 아카이브 ----------
def _zip_rows(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = []
    for r in csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]))):
        if r and r[0].isdigit():
            rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])))
    return rows


def _cached(path, url, keep):
    f = os.path.join(CACHE, path)
    if os.path.exists(f):
        return json.load(open(f))
    raw = get(url)
    rows = _zip_rows(raw) if raw else []
    if keep:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump(rows, open(f, "w"))
    return rows


def arch_klines(sym, interval, start, end):
    """start~end(포함, UTC 날짜) 구간. 끝난 달은 월 파일, 이번 달이나 월 파일이 없으면 일 파일."""
    today = utc_today()
    this_month = dt.date(today.year, today.month, 1)
    rows, d = [], dt.date(start.year, start.month, 1)
    while d <= end:
        nxt = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        ym = d.strftime("%Y-%m")
        got = []
        if nxt <= this_month:
            got = _cached(f"{sym}/{interval}/{ym}.json",
                          f"{ARCH}/monthly/klines/{sym}/{interval}/{sym}-{interval}-{ym}.zip", True)
        recent_month = nxt > this_month - dt.timedelta(days=28)
        if not got and recent_month:  # 월 파일이 아직 안 나온 최근 달만 일 파일로
            day = max(d, start)
            while day < nxt and day <= end:
                ds = day.isoformat()
                got += _cached(f"{sym}/{interval}/{ds}.json",
                               f"{ARCH}/daily/klines/{sym}/{interval}/{sym}-{interval}-{ds}.zip",
                               day <= today - dt.timedelta(days=2))
                day += dt.timedelta(days=1)
        rows += got
        d = nxt
    lo = calendar.timegm(start.timetuple()) * 1000
    hi = calendar.timegm((end + dt.timedelta(days=1)).timetuple()) * 1000
    return sorted({tuple(r) for r in rows if lo <= r[0] < hi})


def arch_symbols():
    syms, marker = [], ""
    while True:
        url = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/daily/klines/&delimiter=/" + (f"&marker={marker}" if marker else "")
        x = get(url).decode()
        syms += re.findall(r"<Prefix>data/futures/um/daily/klines/([^/<]+)/</Prefix>", x)
        m = re.search(r"<NextMarker>([^<]+)</NextMarker>", x)
        if "<IsTruncated>true" in x and m:
            marker = m.group(1)
        else:
            break
    return sorted(s for s in set(syms) if s.endswith("USDT") and "_" not in s)


# ---------- 분석 ----------
def utc_day(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def utc_today():
    return dt.datetime.now(dt.timezone.utc).date()


def analyze(sym, daily, h4, btc_ret7, a):
    V = a.vol * 1e6
    if len(daily) < 45:
        return None
    D = [utc_day(r[0]) for r in daily]
    C = [r[4] for r in daily]; Q = [r[5] for r in daily]
    n = len(daily); w0 = max(0, n - 60)
    bursts = [i for i in range(w0, n) if Q[i] >= V]
    recent = [i for i in bursts if i >= n - a.days]
    if len(recent) < a.min_bursts:
        return None
    first = bursts[0]
    pre = Q[max(0, first - 30):first]
    pre_med = statistics.median(pre) if len(pre) >= 10 else None
    always_big = pre_med is None or pre_med >= V / 3
    base = min(C[max(0, first - 30):first + 1])
    runup = C[-1] / base if base > 0 else 0
    # 첫 폭발 이후 고점 대비 최대 낙폭(급락 후 말아올림 무빙 확인)
    peak, mdd = C[first], 0.0
    for c in C[first:]:
        peak = max(peak, c); mdd = max(mdd, 1 - c / peak)
    hi_since = max(C[first:])
    from_hi = C[-1] / hi_since - 1
    box = C[-10:]
    lo, hi = min(box), max(box)
    pos = (C[-1] - lo) / (hi - lo) if hi > lo else 1.0
    ret7 = C[-1] / C[-8] - 1 if n >= 8 else 0
    # 4시간봉: 최근 12개 중 양봉 수, 저점 높이는 횟수
    bull4 = hl4 = None
    if h4 and len(h4) >= 13:
        last = h4[-12:]
        bull4 = sum(1 for r in last if r[4] > r[1])
        hl4 = sum(1 for p, q in zip(h4[-13:-1], last) if q[3] > p[3])
    flags = []
    if always_big: flags.append("원래 거래량 큰 코인")
    if len(recent) == 1: flags.append("폭발 1번뿐")
    if runup >= 8: flags.append(f"바닥 대비 {runup:.0f}배 · 이미 크게 오름")
    if mdd >= 0.5: flags.append(f"폭발 후 최대 낙폭 -{mdd*100:.0f}%")
    H = [r[2] for r in daily]; L = [r[3] for r in daily]; O = [r[1] for r in daily]
    wicks = sum(1 for i in range(n - 30, n) if (H[i] - max(O[i], C[i])) / C[i] >= 0.25 or (min(O[i], C[i]) - L[i]) / C[i] >= 0.25)
    if wicks >= 3: flags.append(f"25% 넘는 꼬리 {wicks}일(무빙 거침)")
    if from_hi <= -0.4: flags.append("고점 대비 -40% 이하")
    if btc_ret7 is not None and btc_ret7 < -0.03 and ret7 > btc_ret7 + 0.05: flags.append("BTC 하락 중 버팀")
    if pos >= 0.85 and C[-1] < hi_since * 0.98: flags.append("10일 박스 상단")
    if C[-1] >= hi_since * 0.98: flags.append("폭발 후 최고가 부근")
    return dict(
        symbol=sym, base=base_asset(sym), close=C[-1], vol_today=Q[-1] / 1e6,
        bursts_recent=len(recent), first_burst=D[first].isoformat(), last_burst=D[bursts[-1]].isoformat(),
        max_burst=max(Q[i] for i in bursts) / 1e6, pre_median=(pre_med or 0) / 1e6,
        runup=runup, mdd=mdd, from_hi=from_hi, box_pos=pos, ret7=ret7, bull4=bull4, hl4=hl4,
        always_big=always_big, flags=flags)


def main():
    ap = argparse.ArgumentParser(description="강고양이 매매법 기준 바이낸스 선물 스크리너")
    ap.add_argument("--vol", type=float, default=300, help="거래대금 폭발 기준, 단위 M USDT (기본 300)")
    ap.add_argument("--days", type=int, default=30, help="폭발을 셀 최근 일수 (기본 30)")
    ap.add_argument("--min-bursts", type=int, default=1, help="최근 폭발 최소 횟수 (기본 1)")
    ap.add_argument("--source", choices=["api", "archive"], default="api")
    ap.add_argument("--asof", help="아카이브 기준일 YYYY-MM-DD (기본: 이틀 전)")
    ap.add_argument("--include-kr", action="store_true", help="업비트·빗썸 상장 코인도 보여주기")
    ap.add_argument("--include-big", action="store_true", help="원래 거래량이 큰 코인도 보여주기")
    ap.add_argument("--out", default="screener_result.csv", help="CSV 저장 경로")
    a = ap.parse_args()

    kr = korean_listed()
    if a.source == "api":
        syms = api_symbols()
        asof = utc_today()
        fetch_d = lambda s: api_klines(s, "1d", 120)
        fetch_4 = lambda s: api_klines(s, "4h", 30)
    else:
        asof = dt.date.fromisoformat(a.asof) if a.asof else utc_today() - dt.timedelta(days=2)
        syms = arch_symbols()
        start = asof - dt.timedelta(days=110)
        fetch_d = lambda s: arch_klines(s, "1d", start, asof)
        fetch_4 = lambda s: arch_klines(s, "4h", asof - dt.timedelta(days=4), asof)
    cand = [s for s in syms if base_asset(s) not in SKIP and (a.include_kr or base_asset(s) not in kr)]
    print(f"[{a.source}] 기준일 {asof} · 대상 {len(cand)}개 (국내 상장 {'포함' if a.include_kr else '제외'}) · 폭발 기준 {a.vol:.0f}M", file=sys.stderr)

    btc = fetch_d("BTCUSDT")
    btc_ret7 = btc[-1][4] / btc[-8][4] - 1 if len(btc) >= 8 else None

    def run(s):
        if a.source == "archive" and not _cached(f"{s}/1d/{asof.isoformat()}.json",
                f"{ARCH}/daily/klines/{s}/1d/{s}-1d-{asof.isoformat()}.zip", asof <= utc_today() - dt.timedelta(days=2)):
            return None  # 기준일에 거래가 없던 종목
        d = fetch_d(s)
        if a.source == "archive" and d and utc_day(d[-1][0]) != asof:
            return None  # 기준일에 거래가 없던(상장 전·상폐) 종목
        r = analyze(s, d, None, btc_ret7, a)
        if r and (a.include_big or not r["always_big"]):
            r = analyze(s, d, fetch_4(s), btc_ret7, a)
        return r
    res = []
    with ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(run, cand), 1):
            if r and (a.include_big or not r["always_big"]):
                res.append(r)
            if i % 100 == 0:
                print(f"  {i}/{len(cand)}", file=sys.stderr)
    res.sort(key=lambda r: (r["last_burst"], r["bursts_recent"]), reverse=True)

    hdr = ["종목", "종가", "최근 폭발", "첫 폭발", "마지막 폭발", "최대(M)", "폭발 전 중간값(M)", "바닥 대비",
           "고점 대비", "10일 박스 위치", "7일 수익률", "4h 양봉/12", "4h 저점상승/12", "메모"]
    rows = [[r["base"], f"{r['close']:.6g}", r["bursts_recent"], r["first_burst"], r["last_burst"], f"{r['max_burst']:,.0f}",
             f"{r['pre_median']:,.0f}", f"{r['runup']:.1f}배", f"{r['from_hi']*100:+.0f}%", f"{r['box_pos']*100:.0f}%",
             f"{r['ret7']*100:+.0f}%", "-" if r["bull4"] is None else r["bull4"], "-" if r["hl4"] is None else r["hl4"],
             " · ".join(r["flags"])] for r in res]
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows([hdr] + rows)
    print(f"\n{len(res)}개 · BTC 7일 {btc_ret7*100:+.1f}% · CSV: {a.out}\n")
    for r in rows:
        print(f"{r[0]:<12} 폭발 {r[2]}회 ({r[3]}~{r[4]}, 최대 {r[5]}M) · 바닥 대비 {r[7]} · 고점 대비 {r[8]} · 박스 {r[9]} · 7일 {r[10]}\n             {r[13]}")


if __name__ == "__main__":
    main()
