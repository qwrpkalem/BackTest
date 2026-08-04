# -*- coding: utf-8 -*-
"""KRX 원본 응답 확인 — 왜 전종목 조회가 비는지."""
import json

import requests

HDR_OLD = {"User-Agent": "Mozilla/5.0"}
HDR_NEW = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd",
    "X-Requested-With": "XMLHttpRequest",
}
URLS = [
    "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
    "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
]

# 전종목 시세 (거래대금 포함) / 상장종목검색
PAYLOADS = {
    "전종목시세(MDCSTAT01501)": {
        "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
        "mktId": "ALL", "trdDd": "20240102", "share": "1", "money": "1",
    },
    "상장종목검색(MDCSTAT01901)": {
        "bld": "dbms/comm/finder/finder_stkisu",
        "mktsel": "ALL", "typeNo": "0", "searchText": "",
    },
}

for name, payload in PAYLOADS.items():
    for url in URLS:
        for hname, hdr in (("OLD", HDR_OLD), ("NEW", HDR_NEW)):
            try:
                r = requests.post(url, data=payload, headers=hdr, timeout=20)
                body = r.text
                ok = "?"
                try:
                    j = json.loads(body)
                    keys = list(j.keys())
                    n = 0
                    for k in keys:
                        if isinstance(j[k], list):
                            n = max(n, len(j[k]))
                    ok = "json keys=%s maxlist=%d" % (keys[:4], n)
                except Exception:
                    ok = "NOT-JSON len=%d head=%r" % (len(body), body[:80])
                print("%-28s %-6s %-5s HTTP%-4s %s"
                      % (name, hname, url.split(":")[0], r.status_code, ok))
            except Exception as e:
                print("%-28s %-6s %-5s ERR %s" % (name, hname, url.split(":")[0], str(e)[:60]))
