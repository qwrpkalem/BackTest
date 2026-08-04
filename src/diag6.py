# -*- coding: utf-8 -*-
"""근사 방식 검증.

(1) 네이버 일봉의 거래량이 액면분할에 맞춰 조정되는가?
    -> 삼성전자 2018-05-04 50:1 분할 전후 확인
(2) 네이버 시가총액 순위 페이지에서 KOSPI/KOSDAQ 전 종목을 긁을 수 있는가?
"""
import io
import json
import re

import pandas as pd
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
H = {"User-Agent": UA}


def naver_ohlcv(code, start, end):
    u = ("https://api.finance.naver.com/siseJson.naver?symbol=%s&requestType=1"
         "&startTime=%s&endTime=%s&timeframe=day" % (code, start, end))
    txt = requests.get(u, headers=H, timeout=30).text
    txt = txt.replace("'", '"').strip()
    rows = json.loads(txt)
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["날짜"] = pd.to_datetime(df["날짜"], format="%Y%m%d")
    return df.set_index("날짜")


print("=" * 78)
print("(1) 삼성전자 액면분할(2018-05-04, 50:1) 전후 — 거래량 조정 여부")
print("=" * 78)
df = naver_ohlcv("005930", "20180425", "20180515")
print(df.to_string())
pre = df.loc[:"2018-05-03", "거래량"]
post = df.loc["2018-05-04":, "거래량"]
print("\n  분할 전 평균 거래량: %,.0f".replace(",", "") % pre.mean())
print("  분할 후 평균 거래량: %.0f" % post.mean())
print("  비율(후/전): %.1f배   -> 50배 근처면 거래량은 '미조정'(실제 체결주식수)"
      % (post.mean() / pre.mean()))
print("  종가 확인: 분할 전 종가 %.0f  분할 후 종가 %.0f"
      % (df.loc[:"2018-05-03", "종가"].iloc[-1], df.loc["2018-05-04":, "종가"].iloc[0]))

print()
print("=" * 78)
print("(2) 네이버 시가총액 순위 — KOSPI(sosok=0) / KOSDAQ(sosok=1) 페이지 수집")
print("=" * 78)
for sosok, nm in ((0, "KOSPI"), (1, "KOSDAQ")):
    u = ("https://finance.naver.com/sise/sise_market_sum.naver?sosok=%d&page=1" % sosok)
    r = requests.get(u, headers=H, timeout=30)
    r.encoding = "euc-kr"
    # 마지막 페이지 번호
    pages = re.findall(r"page=(\d+)", r.text)
    last = max(int(p) for p in pages) if pages else 1
    tables = pd.read_html(io.StringIO(r.text))
    t = None
    for cand in tables:
        if "시가총액" in [str(c) for c in cand.columns]:
            t = cand.dropna(how="all").dropna(subset=["종목명"])
            break
    # 종목코드는 링크에서 추출
    codes = re.findall(r"/item/main\.naver\?code=(\d{6})", r.text)
    print("  %-6s 마지막페이지=%-4d  1페이지 종목수=%-3d  코드추출=%d개"
          % (nm, last, len(t) if t is not None else -1, len(set(codes))))
    if t is not None:
        print("     cols=%s" % list(t.columns))
        print(t.head(2).to_string()[:400])
