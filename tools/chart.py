#!/usr/bin/env python3
"""종목 하나의 일봉·4시간봉·1시간봉을 보기 좋게 출력해요. Claude가 차트를 읽을 때 씁니다.

사용 예:
  python tools/chart.py MUBARAK            # 실시간 API (한국 등)
  python tools/chart.py AIN --source archive
  python tools/chart.py SYN --days 90 --h4 60 --h1 0
"""
import argparse, datetime as dt, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screener as S

KST = dt.timedelta(hours=9)


def fmt(v):
    return f"{v:.6g}"


def show(title, rows, kst=True, n=None):
    rows = rows[-n:] if n else rows
    print(f"\n## {title} ({len(rows)}개, {'한국 시간' if kst else 'UTC 날짜'}, 거래대금 M USDT)")
    print("시각            시가        고가        저가        종가        거래대금  등락")
    for r in rows:
        t = dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone.utc) + (KST if kst else dt.timedelta())
        chg = (r[4] / r[1] - 1) * 100 if r[1] else 0
        print(f"{t:%m-%d %H:%M}  {fmt(r[1]):>10}  {fmt(r[2]):>10}  {fmt(r[3]):>10}  {fmt(r[4]):>10}  {r[5]/1e6:>8.1f}  {chg:+.1f}%")


def main():
    ap = argparse.ArgumentParser(description="종목 차트 데이터 출력")
    ap.add_argument("coin", help="코인 이름 (예: MUBARAK) 또는 심볼 (MUBARAKUSDT)")
    ap.add_argument("--source", choices=["api", "archive"], default="api")
    ap.add_argument("--days", type=int, default=60, help="일봉 개수")
    ap.add_argument("--h4", type=int, default=42, help="4시간봉 개수 (0이면 생략)")
    ap.add_argument("--h1", type=int, default=24, help="1시간봉 개수 (0이면 생략)")
    a = ap.parse_args()
    sym = a.coin.upper()
    if not sym.endswith("USDT"):
        sym += "USDT"
    base = S.base_asset(sym)

    kr = S.korean_listed()
    print(f"# {sym} · 국내 상장: {'있음 (업비트 원화·BTC·USDT 또는 빗썸)' if base in kr else '없음'} · 데이터: {a.source}")

    if a.source == "api":
        d = S.api_klines(sym, "1d", a.days + 30)
        h4 = S.api_klines(sym, "4h", a.h4) if a.h4 else []
        h1 = S.api_klines(sym, "1h", a.h1) if a.h1 else []
    else:
        end = S.utc_today() - dt.timedelta(days=1)
        d = S.arch_klines(sym, "1d", end - dt.timedelta(days=a.days + 30), end)
        h4 = S.arch_klines(sym, "4h", end - dt.timedelta(days=a.h4 // 6 + 2), end)[-a.h4:] if a.h4 else []
        h1 = S.arch_klines(sym, "1h", end - dt.timedelta(days=a.h1 // 24 + 2), end)[-a.h1:] if a.h1 else []
    if not d:
        sys.exit("데이터가 없어요. 심볼을 확인하세요.")

    Q = [r[5] for r in d]; C = [r[4] for r in d]
    big = [(S.utc_day(r[0]).isoformat(), r[5] / 1e6) for r in d[-60:] if r[5] >= 300e6]
    print(f"최근 60일 300M 이상인 날: {len(big)}일 " + (", ".join(f"{x} {v:,.0f}M" for x, v in big) if big else ""))
    if len(Q) > 40:
        print(f"60일 전~30일 전 거래대금 중간값: {statistics.median(Q[-60:-30])/1e6:,.1f}M · 최근 7일 평균: {sum(Q[-7:])/7/1e6:,.1f}M")
    print(f"60일 최고 종가 {fmt(max(C[-60:]))} · 최저 종가 {fmt(min(C[-60:]))} · 지금 {fmt(C[-1])}")
    btc = S.api_klines("BTCUSDT", "1d", 10) if a.source == "api" else S.arch_klines("BTCUSDT", "1d", S.utc_today() - dt.timedelta(days=12), S.utc_today() - dt.timedelta(days=1))
    if len(btc) >= 8 and len(C) >= 8:
        print(f"7일 수익률: 이 코인 {(C[-1]/C[-8]-1)*100:+.1f}% · BTC {(btc[-1][4]/btc[-8][4]-1)*100:+.1f}%")
    show("일봉", d, kst=False, n=a.days)
    if h4:
        show("4시간봉", h4)
    if h1:
        show("1시간봉", h1)
    if a.source == "api":
        print("\n(마지막 봉은 아직 진행 중일 수 있어요)")


if __name__ == "__main__":
    main()
