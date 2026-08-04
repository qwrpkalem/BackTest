# -*- coding: utf-8 -*-
"""다음 금융 API 실용성 검증: perPage 한계 / 과거 데이터 깊이 / 수정주가 여부."""
import time
import traceback

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

s = requests.Session()
s.headers.update({"User-Agent": UA, "Referer": "https://finance.daum.net/quotes/A005930"})
URL = "https://finance.daum.net/api/quote/A005930/days"


def fetch(page, per):
    t = time.time()
    r = s.get(URL, params={"symbolCode": "A005930", "page": page,
                           "perPage": per, "pagination": "true"}, timeout=30)
    el = time.time() - t
    if r.status_code != 200:
        return None, el, r.status_code
    return r.json(), el, 200


print("=" * 74)
print("A. perPage 상한 탐색")
print("=" * 74)
for per in (10, 100, 500, 1000, 3000):
    try:
        j, el, code = fetch(1, per)
        if j is None:
            print("  perPage=%-5d HTTP%s" % (per, code))
            continue
        d = j.get("data", [])
        print("  perPage=%-5d -> rows=%-5d %.2fs  first=%s last=%s"
              % (per, len(d), el,
                 d[0]["date"][:10] if d else "-", d[-1]["date"][:10] if d else "-"))
    except Exception as e:
        print("  perPage=%-5d ERR %s" % (per, str(e)[:60]))
    time.sleep(0.3)

print()
print("=" * 74)
print("B. 과거 깊이 — 2015년까지 도달 가능한가 (perPage=100 기준 페이지 이동)")
print("=" * 74)
try:
    for page in (1, 10, 20, 27, 30):
        j, el, code = fetch(page, 100)
        d = j.get("data", []) if j else []
        print("  page=%-3d rows=%-4d %.2fs  %s ~ %s"
              % (page, len(d), el,
                 d[0]["date"][:10] if d else "-", d[-1]["date"][:10] if d else "-"))
        time.sleep(0.3)
except Exception:
    traceback.print_exc(limit=2)

print()
print("=" * 74)
print("C. 수정주가 여부 — 삼성전자 2018-05-04 50:1 분할 전후")
print("=" * 74)
try:
    # 2018-05 근처가 나올 만한 페이지를 넓게 훑어서 해당 날짜 찾기
    found = {}
    for page in range(18, 24):
        j, el, code = fetch(page, 100)
        d = j.get("data", []) if j else []
        for row in d:
            ds = row["date"][:10]
            if ds in ("2018-04-27", "2018-05-04", "2018-05-08"):
                found[ds] = row
        if found and len(found) >= 3:
            break
        time.sleep(0.3)
    for k in sorted(found):
        r = found[k]
        print("  %s  종가=%-12s 거래량=%-12s 거래대금=%-16s 상장주식수=%s"
              % (k, r["tradePrice"], r["accTradeVolume"],
                 r["accTradePrice"], r.get("listedSharesCount")))
    if "2018-04-27" in found and "2018-05-08" in found:
        a = found["2018-04-27"]["tradePrice"]
        b = found["2018-05-08"]["tradePrice"]
        print("\n  분할 전 종가 %.0f / 분할 후 종가 %.0f  -> 비율 %.1f" % (a, b, a / b))
        print("  비율이 50 근처면 '원주가(미조정)', 1 근처면 '수정주가'")
except Exception:
    traceback.print_exc(limit=2)
