#!/usr/bin/env python3
"""강고양이식 진입을 흉내 낸 과거 복기: 폭발 → 거래량 마른 박스 → 거래량 실린 박스 돌파에 진입, 박스 하단 손절.

backtest.py를 먼저 한 번 돌려서 tools/.cache에 일봉이 받아져 있어야 빨라요.
결과: tools/.cache/backtest_setup.json
"""
import argparse, datetime as dt, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screener as S
from backtest import load_all, TRADES

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-10-01")
    ap.add_argument("--end")
    ap.add_argument("--vol", type=float, default=300, help="폭발 기준 (M USDT)")
    ap.add_argument("--min-box", type=int, default=3, help="박스 최소 일수")
    ap.add_argument("--max-box", type=int, default=30, help="폭발 뒤 박스를 찾는 최대 일수")
    ap.add_argument("--box-range", type=float, default=0.5, help="박스 고저폭 상한 (0.5 = 50%)")
    ap.add_argument("--dry", type=float, default=0.35, help="박스 거래대금 중간값 / 폭발일 거래대금 상한")
    ap.add_argument("--trig", type=float, default=1.5, help="돌파일 거래대금 / 박스 중간값 하한")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    start = dt.date.fromisoformat(a.start)
    end = dt.date.fromisoformat(a.end) if a.end else S.utc_today() - dt.timedelta(days=2)
    V = a.vol * 1e6
    kr = S.korean_listed(); skip = S.SKIP | S.STOCKS
    data = load_all(start, end, a.workers)

    out = []
    for s, rows in data.items():
        base = S.base_asset(s)
        if base in skip or base in kr:
            continue
        D = [S.utc_day(r[0]) for r in rows]
        O = [r[1] for r in rows]; H = [r[2] for r in rows]; L = [r[3] for r in rows]; C = [r[4] for r in rows]; Q = [r[5] for r in rows]
        last_entry = -999
        for b in range(30, len(rows)):
            if Q[b] < V or D[b] < start - dt.timedelta(days=a.max_box) or D[b] > end:
                continue
            pre = Q[max(0, b - 30):b]
            if len(pre) < 10 or statistics.median(pre) >= V / 3:
                continue  # 원래 거래량 큰 코인
            for k in range(b + a.min_box + 1, min(len(rows), b + a.max_box + 1)):
                box = range(b + 1, k)
                bh = max(H[i] for i in box); bl = min(L[i] for i in box)
                if bh / bl - 1 > a.box_range:
                    break  # 박스가 너무 넓어지면 이 폭발은 포기
                bq = statistics.median(Q[i] for i in box)
                if bq > a.dry * Q[b]:
                    continue  # 아직 거래량이 안 마름
                if C[k] > bh and Q[k] >= a.trig * bq and D[k] >= start and D[k] <= end and k - last_entry > 14:
                    entry, sl = C[k], bl
                    fw = list(range(k + 1, min(len(rows), k + 61)))
                    first = "진행 중"
                    for i in fw:
                        if L[i] <= sl and H[i] >= 2 * entry: first = "같은 날 둘 다"; break
                        if L[i] <= sl: first = "손절선 먼저"; break
                        if H[i] >= 2 * entry: first = "2배 먼저"; break
                    else:
                        if len(fw) >= 60: first = "60일 안에 둘 다 없음"
                    mx = lambda n: max(C[i] for i in fw[:n]) / entry if len(fw) >= n else None
                    mn = lambda n: min(C[i] for i in fw[:n]) / entry if len(fw) >= n else None
                    # 손절 전까지 최고 (손절에 걸리기 전 얼마나 갔나)
                    best = 1.0
                    for i in fw:
                        if L[i] <= sl: break
                        best = max(best, H[i] / entry)
                    his = any(abs((D[k] - dt.date.fromisoformat(t)).days) <= 10 for t in TRADES.get(base, []))
                    out.append(dict(sym=s, base=base, burst=D[b].isoformat(), burst_vol=round(Q[b] / 1e6),
                                    box_start=D[b + 1].isoformat(), box_days=k - b - 1, box_hi=bh, box_lo=bl,
                                    box_range=round(bh / bl - 1, 3), box_vol=round(bq / 1e6, 1),
                                    date=D[k].isoformat(), entry=entry, entry_vol=round(Q[k] / 1e6),
                                    sl=sl, sl_pct=round(sl / entry - 1, 3), runup=round(entry / min(C[max(0, b - 30):b + 1]), 2),
                                    max30=mx(30), max60=mx(60), min60=mn(60), best_before_sl=round(best, 2), first=first, his=his))
                    last_entry = k
                    break
    out.sort(key=lambda e: e["date"])
    json.dump(dict(start=start.isoformat(), end=end.isoformat(), params=vars(a), events=out),
              open(os.path.join(HERE, ".cache", "backtest_setup.json"), "w", encoding="utf-8"), ensure_ascii=False)
    done = [e for e in out if e["first"] != "진행 중"]
    print(f"박스 돌파 진입 {len(out)}건 (결과 확인 {len(done)}건)")
    from collections import Counter
    print(" ", dict(Counter(e["first"] for e in done)))
    if done:
        print(f"  손절폭 중간값 {sorted(e['sl_pct'] for e in done)[len(done)//2]*100:.0f}%")


if __name__ == "__main__":
    main()
