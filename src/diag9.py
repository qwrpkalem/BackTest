# -*- coding: utf-8 -*-
"""수집 안정성 검증: 코스닥 종목 / 연속 호출 차단 여부 / 네이버-다음 날짜 정합성."""
import json
import time

import pandas as pd
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

ds = requests.Session()
ds.headers.update({"User-Agent": UA, "Referer": "https://finance.daum.net/"})


def daum(code, per=3000):
    r = ds.get("https://finance.daum.net/api/quote/A%s/days" % code,
               params={"symbolCode": "A" + code, "page": 1, "perPage": per,
                       "pagination": "true"}, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def naver(code, start="20150101", end="20260803"):
    u = ("https://api.finance.naver.com/siseJson.naver?symbol=%s&requestType=1"
         "&startTime=%s&endTime=%s&timeframe=day" % (code, start, end))
    txt = requests.get(u, headers={"User-Agent": UA}, timeout=30).text
    rows = json.loads(txt.replace("'", '"').strip())
    return pd.DataFrame(rows[1:], columns=rows[0])


print("=" * 74)
print("A. 시장별 샘플 종목")
print("=" * 74)
SAMPLES = [("005930", "삼성전자/KOSPI"), ("035720", "카카오/KOSPI"),
           ("247540", "에코프로비엠/KOSDAQ"), ("196170", "알테오젠/KOSDAQ"),
           ("000660", "SK하이닉스/KOSPI")]
for code, nm in SAMPLES:
    try:
        d = daum(code)
        oldest, newest = d[-1]["date"][:10], d[0]["date"][:10]
        mc = d[0]["tradePrice"] * d[0]["listedSharesCount"] / 1e12
        print("  %-8s %-18s rows=%-5d %s ~ %s  현재시총=%.1f조"
              % (code, nm, len(d), oldest, newest, mc))
    except Exception as e:
        print("  %-8s %-18s FAIL %s" % (code, nm, str(e)[:60]))
    time.sleep(0.2)

print()
print("=" * 74)
print("B. 연속 호출 30회 — 차단/지연 발생 여부 (딜레이 0.15s)")
print("=" * 74)
codes = ["005930", "000660", "035720", "051910", "006400", "005380", "000270",
         "068270", "207940", "005490", "012330", "028260", "066570", "015760",
         "032830", "018260", "003550", "017670", "034730", "096770", "010950",
         "011200", "009150", "010130", "011170", "047050", "004020", "001040",
         "008930", "086790"]
ok = fail = 0
t0 = time.time()
lat = []
for i, c in enumerate(codes):
    try:
        t = time.time()
        d = daum(c, per=3000)
        lat.append(time.time() - t)
        ok += 1
        if not d:
            print("  [%2d] %s EMPTY" % (i, c))
    except Exception as e:
        fail += 1
        print("  [%2d] %s FAIL %s" % (i, c, str(e)[:70]))
    time.sleep(0.15)
print("  성공=%d 실패=%d  총 %.1fs  평균응답 %.3fs  최대 %.3fs"
      % (ok, fail, time.time() - t0, sum(lat) / max(len(lat), 1), max(lat or [0])))
print("  -> 전 종목(2872개) 예상 소요: %.1f분" % (2872 * (sum(lat) / max(len(lat), 1) + 0.15) / 60))

print()
print("=" * 74)
print("C. 네이버(수정주가) vs 다음(원주가) 날짜 정합성 — 삼성전자")
print("=" * 74)
try:
    n = naver("005930")
    d = daum("005930")
    nd = set(n["날짜"].astype(str))
    dd = set(x["date"][:10].replace("-", "") for x in d)
    common = nd & dd
    print("  네이버 %d일 / 다음 %d일 / 공통 %d일" % (len(nd), len(dd), len(common)))
    print("  네이버에만: %d일  다음에만: %d일" % (len(nd - dd), len(dd - nd)))
    only_n = sorted(nd - dd)[-5:]
    only_d = sorted(dd - nd)[-5:]
    print("  네이버 단독 샘플: %s" % only_n)
    print("  다음  단독 샘플: %s" % only_d)
    # 거래정지(0값) 행 개수
    zero = n[(n["종가"] == 0) | (n["거래량"] == 0)]
    print("  네이버 0값(거래정지 등) 행: %d개" % len(zero))
except Exception as e:
    print("  FAIL", str(e)[:100])
