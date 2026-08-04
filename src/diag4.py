# -*- coding: utf-8 -*-
"""세션 쿠키 확보 후 KRX 전종목/개별종목 조회 재시도."""
import json

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
INDEX = "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"
POST = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

s = requests.Session()
s.headers.update({
    "User-Agent": UA,
    "Referer": INDEX,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
})
# 세션 쿠키 확보
r0 = s.get(INDEX, params={"menuId": "MDC0201020101"}, timeout=20)
print("index GET: HTTP%s  cookies=%s" % (r0.status_code, s.cookies.get_dict()))


def call(label, payload):
    try:
        r = s.post(POST, data=payload, timeout=30)
        try:
            j = json.loads(r.text)
        except Exception:
            print("  %-32s HTTP%s NOT-JSON: %r" % (label, r.status_code, r.text[:60]))
            return None
        rows = None
        for k, v in j.items():
            if isinstance(v, list) and v:
                rows = v
                print("  %-32s HTTP%s  key=%s n=%d" % (label, r.status_code, k, len(v)))
                print("      cols: %s" % list(v[0].keys()))
                print("      row0: %s" % json.dumps(v[0], ensure_ascii=False)[:300])
                break
        if rows is None:
            print("  %-32s HTTP%s  EMPTY %s" % (label, r.status_code, list(j.keys())))
        return rows
    except Exception as e:
        print("  %-32s ERR %s" % (label, str(e)[:80]))
        return None


print("\n=== 전종목시세 (시가총액·거래대금 포함) ===")
call("MDCSTAT01501 20240102", {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
    "mktId": "ALL", "trdDd": "20240102", "share": "1", "money": "1", "csvxls_isNo": "false",
})

print("\n=== 개별종목 일자별 시세 (거래대금 포함) ===")
call("MDCSTAT01701 삼성 2024", {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT01701",
    "isuCd": "KR7005930003", "strtDd": "20240102", "endDd": "20240131",
    "share": "1", "money": "1", "adjStkPrc": "2", "csvxls_isNo": "false",
})

print("\n=== 상장종목 검색 (티커 목록) ===")
call("finder_stkisu", {
    "bld": "dbms/comm/finder/finder_stkisu",
    "mktsel": "ALL", "typeNo": "0", "searchText": "",
})
