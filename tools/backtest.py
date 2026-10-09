#!/usr/bin/env python3
"""스크리너 기준을 지난 1년 매일 날짜에 적용해 "후보 등장" 사례와 그 뒤 결과를 모아요.

미래 정보는 쓰지 않아요. 각 날짜에는 그날 종가까지의 데이터만 써서 판단하고, 결과는 그 뒤 데이터로 붙여요.

사용 예:
  python tools/backtest.py                       # 2025-10-01부터 어제까지
  python tools/backtest.py --start 2026-01-01 --vol 350
결과: tools/.cache/backtest.json (차트·요약 생성용)
"""
import argparse, datetime as dt, json, os, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screener as S

HERE = os.path.dirname(os.path.abspath(__file__))
TRADES = {  # 강고양이 실제 매매 (진입 또는 매매 시점, KST 날짜 기준 대략)
    "COAI": ["2025-10-06"], "AIA": ["2025-10-02"], "XPIN": ["2025-10-20"], "TNSR": ["2025-11-19"],
    "PIPPIN": ["2025-11-23", "2025-12-01", "2025-12-15"], "BULLA": ["2026-01-31"], "SIREN": ["2026-03-19"],
    "STO": ["2026-04-01"], "SKYAI": ["2026-04-29"], "SYN": ["2026-06-21"], "AKE": ["2026-07-20", "2026-09-01"],
}


def load_all(start, end, workers):
    syms = S.arch_symbols()
    a = start - dt.timedelta(days=110)

    def one(s):
        try:
            return s, S.arch_klines(s, "1d", a, end)
        except Exception:
            return s, []
    out = {}
    with ThreadPoolExecutor(workers) as ex:
        for i, (s, rows) in enumerate(ex.map(one, syms), 1):
            if len(rows) >= 50:
                out[s] = rows
            if i % 100 == 0:
                print(f"  데이터 {i}/{len(syms)}", file=sys.stderr, flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="스크리너 기준 과거 1년 복기")
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end", help="마지막 판단일 (기본: 이틀 전)")
    ap.add_argument("--vol", type=float, default=300)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--min-bursts", type=int, default=1)
    ap.add_argument("--gap", type=int, default=14, help="같은 종목을 다시 '새 등장'으로 치는 최소 공백 일수")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else S.utc_today() - dt.timedelta(days=2)

    kr = S.korean_listed()
    skip = S.SKIP | S.STOCKS
    print(f"과거 데이터 받는 중 ({start} ~ {end}) …", file=sys.stderr)
    data = load_all(start, end, a.workers)
    btc = {S.utc_day(r[0]): r[4] for r in data.get("BTCUSDT", [])}
    btc_days = sorted(btc)

    def btc_ret7(d):
        prev = d - dt.timedelta(days=7)
        if d in btc and prev in btc:
            return btc[d] / btc[prev] - 1
        return None

    events = []
    for s, rows in data.items():
        base = S.base_asset(s)
        if base in skip or base in kr:
            continue
        D = [S.utc_day(r[0]) for r in rows]
        last_hit = None
        for i in range(45, len(rows)):
            d = D[i]
            if d < start or d > end:
                continue
            r = S.analyze(s, rows[:i + 1], None, btc_ret7(d), a)
            if not r or r["always_big"]:
                continue
            new = last_hit is None or (d - last_hit).days > a.gap
            last_hit = d
            if not new:
                continue
            c = rows[i][4]
            fw = rows[i + 1:i + 61]
            lows10 = min(x[3] for x in rows[max(0, i - 9):i + 1])
            first = "진행 중"
            for k, x in enumerate(fw):
                hit_sl, hit_2x = x[3] <= lows10, x[2] >= 2 * c
                if hit_sl and hit_2x:
                    first = "같은 날 둘 다"; break
                if hit_sl:
                    first = "손절선 먼저"; break
                if hit_2x:
                    first = "2배 먼저"; break
            else:
                if len(fw) >= 60:
                    first = "60일 안에 둘 다 없음"
            def mx(n):
                w = fw[:n]
                return max(x[4] for x in w) / c if len(w) >= n else None
            def mn(n):
                w = fw[:n]
                return min(x[4] for x in w) / c if len(w) >= n else None
            his = any(abs((d - dt.date.fromisoformat(t)).days) <= 10 for t in TRADES.get(base, []))
            events.append(dict(
                sym=s, base=base, date=d.isoformat(), close=c, sl=lows10, sl_pct=lows10 / c - 1,
                bursts=r["bursts_recent"], first_burst=r["first_burst"], last_burst=r["last_burst"],
                max_burst=round(r["max_burst"]), pre_median=round(r["pre_median"], 1), runup=round(r["runup"], 2),
                mdd=round(r["mdd"], 3), from_hi=round(r["from_hi"], 3), box_pos=round(r["box_pos"], 2),
                ret7=round(r["ret7"], 3), btc7=None if btc_ret7(d) is None else round(btc_ret7(d), 3),
                flags=r["flags"], max30=mx(30), max60=mx(60), min30=mn(30), min60=mn(60), first=first, his=his))
    events.sort(key=lambda e: e["date"])
    os.makedirs(os.path.join(HERE, ".cache"), exist_ok=True)
    json.dump(dict(start=start.isoformat(), end=end.isoformat(), vol=a.vol, events=events),
              open(os.path.join(HERE, ".cache", "backtest.json"), "w", encoding="utf-8"), ensure_ascii=False)
    done = [e for e in events if e["max60"] is not None]
    print(f"\n후보 등장 {len(events)}건 (60일 결과 확인 가능 {len(done)}건)")
    if done:
        for lab, f in [("60일 안에 2배 이상", lambda e: e["max60"] >= 2), ("60일 안에 3배 이상", lambda e: e["max60"] >= 3),
                       ("60일 안에 반토막", lambda e: e["min60"] <= 0.5)]:
            print(f"  {lab}: {sum(map(f, done))}건 ({100*sum(map(f, done))/len(done):.0f}%)")
        from collections import Counter
        print("  손절선 vs 2배 먼저:", dict(Counter(e["first"] for e in done)))


if __name__ == "__main__":
    main()
