#!/usr/bin/env python3
"""관심 종목 차트 데이터를 바이낸스 실시간 API로 받아 docs/kangneow-charts-watch.json 으로 저장해요.

사용 예:
  python tools/watch_charts.py MUBARAK RAYSOL
차트 사이트의 "관심 종목" 탭이 이 파일을 읽어요. 저장한 뒤 Claude가 사이트에 다시 올려야 반영돼요.
"""
import datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screener as S

K = 9 * 3600
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "kangneow-charts-watch.json")
LIMITS = {"1M": 100, "1w": 300, "1d": 500, "4h": 1000, "1h": 1000, "15m": 1000, "5m": 1000, "1m": 1000}


def sig(x):
    return float(f"{x:.6g}")


def vol_marks(h1):
    out, win, last = [], [], -10 ** 12
    for r in h1:
        win.append(r[5])
        if len(win) > 24:
            win.pop(0)
        v = sum(win)
        end = r[0] // 1000 + 3600
        if len(win) == 24 and v >= 400e6:
            if end - last > 3 * 86400:
                out.append(dict(t=r[0] // 1000 + K, kind="vol", text=f"24h {v / 1e6:,.0f}M"))
            last = end
    return out


def main():
    bases = [a.upper().replace("USDT", "") for a in sys.argv[1:]]
    if not bases:
        sys.exit("코인 이름을 하나 이상 주세요. 예: python tools/watch_charts.py MUBARAK")
    data = {"asof": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M"), "items": {}}
    for b in bases:
        sym = b + "USDT"
        tf = {}
        for iv, n in LIMITS.items():
            rows = S.api_klines(sym, iv, n)
            tf[iv] = [[r[0] // 1000 + K, sig(r[1]), sig(r[2]), sig(r[3]), sig(r[4]), round(r[5] / 1e6, 4)] for r in rows]
        if not tf["1d"]:
            print(f"{sym}: 데이터 없음 (심볼 확인)")
            continue
        data["items"][b] = dict(sym=sym, tf=tf, vmarks=vol_marks(S.api_klines(sym, "1h", 1500)))
        print(f"{sym}: 일봉 {len(tf['1d'])}개, 1분봉 {len(tf['1m'])}개, 400M 표시 {len(data['items'][b]['vmarks'])}개")
    json.dump(data, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    print("저장:", OUT, round(os.path.getsize(OUT) / 1e6, 2), "MB · 기준", data["asof"])


if __name__ == "__main__":
    main()
