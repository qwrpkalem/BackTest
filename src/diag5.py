# -*- coding: utf-8 -*-
"""시가총액 / 거래대금 확보를 위한 대체 경로 탐색."""
import io
import json
import traceback

import pandas as pd
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def hdr(referer):
    return {"User-Agent": UA, "Referer": referer,
            "X-Requested-With": "XMLHttpRequest"}


print("=" * 70)
print("A. KRX OTP 파일다운로드 플로우 (generate.cmd -> download.cmd)")
print("=" * 70)
try:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    gen = "http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd"
    dl = "http://data.krx.co.kr/comm/fileDn/download_csv/download.cmd"
    ref = "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201020101"
    otp_payload = {
        "locale": "ko_KR", "mktId": "ALL", "trdDd": "20240102",
        "share": "1", "money": "1", "csvxls_isNo": "false",
        "name": "fileDown", "url": "dbms/MDC/STAT/standard/MDCSTAT01501",
    }
    r = s.post(gen, data=otp_payload, headers=hdr(ref), timeout=30)
    print("  generate: HTTP%s len=%d  %r" % (r.status_code, len(r.text), r.text[:80]))
    if r.status_code == 200 and len(r.text) > 20:
        r2 = s.post(dl, data={"code": r.text}, headers=hdr(ref), timeout=60)
        print("  download: HTTP%s len=%d" % (r2.status_code, len(r2.content)))
        try:
            df = pd.read_csv(io.BytesIO(r2.content), encoding="euc-kr")
            print("  ROWS=%d COLS=%s" % (len(df), list(df.columns)))
            print(df.head(3).to_string())
        except Exception:
            print("  csv parse fail:", r2.content[:200])
except Exception:
    traceback.print_exc(limit=2)

print()
print("=" * 70)
print("B. 네이버 시세 API (거래대금 포함 여부)")
print("=" * 70)
try:
    u = ("https://api.finance.naver.com/siseJson.naver?symbol=005930&requestType=1"
         "&startTime=20240102&endTime=20240110&timeframe=day")
    r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
    print("  HTTP%s  %s" % (r.status_code, r.text[:400].replace("\n", " ")))
except Exception:
    traceback.print_exc(limit=2)

print()
print("=" * 70)
print("C. 네이버 시가총액 순위 페이지 (현재 시총)")
print("=" * 70)
try:
    u = "https://finance.naver.com/sise/sise_market_sum.naver?&page=1"
    r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
    r.encoding = "euc-kr"
    tables = pd.read_html(io.StringIO(r.text))
    for t in tables:
        if len(t) > 5:
            t = t.dropna(how="all")
            print("  ROWS=%d COLS=%s" % (len(t), list(t.columns)))
            print(t.head(3).to_string()[:500])
            break
except Exception:
    traceback.print_exc(limit=2)

print()
print("=" * 70)
print("D. FDR StockListing 대체 경로")
print("=" * 70)
import FinanceDataReader as fdr

for key in ["KRX", "KOSPI", "KRX-DESC", "KRX-MARCAP"]:
    try:
        df = fdr.StockListing(key)
        print("  %-12s OK rows=%d cols=%s" % (key, len(df), list(df.columns)[:12]))
    except Exception as e:
        print("  %-12s FAIL %s: %s" % (key, type(e).__name__, str(e)[:60]))

print()
print("=" * 70)
print("E. 네이버 종목 정보 (상장주식수)")
print("=" * 70)
try:
    u = "https://finance.naver.com/item/main.naver?code=005930"
    r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
    r.encoding = "euc-kr"
    txt = r.text
    i = txt.find("상장주식수")
    print("  found at %d: %r" % (i, txt[i - 100:i + 300].replace("\n", " ") if i > 0 else "N/A"))
except Exception:
    traceback.print_exc(limit=2)
