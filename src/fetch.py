# -*- coding: utf-8 -*-
"""데이터 수집.

소스 분담
  - KRX finder    : 종목 리스트 (코드/이름/시장)
  - 다음 금융     : 원주가 OHLC, 실제 거래대금, 상장주식수  -> 시가총액 계산
  - 네이버 siseJson: 수정주가 OHLCV                        -> 신호 계산

수집 결과는 data/ 아래 종목별 CSV로 캐시하며, 재실행 시 이미 받은 종목은 건너뛴다.
"""
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- 종목 리스트
def fetch_ticker_list():
    """KRX finder 로 상장 종목 전체를 받아 보통주만 남긴다."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd",
        "X-Requested-With": "XMLHttpRequest",
    })
    r = s.post("http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
               data={"bld": "dbms/comm/finder/finder_stkisu",
                     "mktsel": "ALL", "typeNo": "0", "searchText": ""}, timeout=30)
    rows = r.json()["block1"]
    df = pd.DataFrame(rows)[["short_code", "codeName", "marketCode", "marketName"]]
    df.columns = ["code", "name", "market_code", "market"]
    n0 = len(df)

    df = df[df["market_code"].isin(C.MARKETS)]                      # KONEX 제외
    n1 = len(df)
    df = df[df["code"].str.endswith("0")]                           # 우선주 제외
    n2 = len(df)
    pat = "|".join(C.EXCLUDE_NAME_TOKENS)
    df = df[~df["name"].str.contains(pat, na=False)]                # 스팩/리츠 제외
    n3 = len(df)

    log("[종목리스트] 전체 %d -> 시장필터 %d -> 우선주제외 %d -> 스팩/리츠제외 %d"
        % (n0, n1, n2, n3))
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 다음 (금액)
def fetch_daum(session, code, retries=3):
    """원주가 OHLC + 거래대금 + 상장주식수. perPage=3000 으로 1회 호출."""
    url = "https://finance.daum.net/api/quote/A%s/days" % code
    for attempt in range(retries):
        try:
            r = session.get(url, params={"symbolCode": "A" + code, "page": 1,
                                         "perPage": 3000, "pagination": "true"},
                            timeout=30)
            if r.status_code != 200:
                time.sleep(1.0 + attempt)
                continue
            data = r.json().get("data", [])
            if not data:
                return None
            df = pd.DataFrame(data)[[
                "date", "openingPrice", "highPrice", "lowPrice", "tradePrice",
                "accTradeVolume", "accTradePrice", "listedSharesCount"]]
            df.columns = ["date", "open_r", "high_r", "low_r", "close_r",
                          "volume", "value", "shares"]
            df["date"] = pd.to_datetime(df["date"].str[:10])
            df = df.sort_values("date").reset_index(drop=True)
            df["marcap"] = df["close_r"] * df["shares"]
            return df
        except Exception:
            time.sleep(1.0 + attempt)
    return None


# ---------------------------------------------------------------- 네이버 (수정주가)
def fetch_naver(code, start, end, retries=3):
    url = ("https://api.finance.naver.com/siseJson.naver?symbol=%s&requestType=1"
           "&startTime=%s&endTime=%s&timeframe=day" % (code, start, end))
    for attempt in range(retries):
        try:
            txt = requests.get(url, headers={"User-Agent": UA}, timeout=30).text
            rows = json.loads(txt.replace("'", '"').strip())
            if len(rows) < 2:
                return None
            df = pd.DataFrame(rows[1:], columns=rows[0])
            df = df[["날짜", "시가", "고가", "저가", "종가", "거래량"]]
            df.columns = ["date", "open", "high", "low", "close", "volume_adj"]
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
            return df.sort_values("date").reset_index(drop=True)
        except Exception:
            time.sleep(1.0 + attempt)
    return None


# ---------------------------------------------------------------- 실행
def run_daum(tickers):
    os.makedirs(C.DAUM_DIR, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://finance.daum.net/"})
    todo = [t for t in tickers if not os.path.exists(
        os.path.join(C.DAUM_DIR, "%s.csv" % t))]
    log("[다음] 대상 %d개 (캐시 %d개 건너뜀)" % (len(todo), len(tickers) - len(todo)))
    t0, fails = time.time(), []
    for i, code in enumerate(todo, 1):
        df = fetch_daum(s, code)
        if df is None or df.empty:
            fails.append(code)
        else:
            df.to_csv(os.path.join(C.DAUM_DIR, "%s.csv" % code), index=False)
        if i % 200 == 0:
            el = time.time() - t0
            log("  %4d/%d  %.1f분 경과  실패 %d  (잔여 약 %.1f분)"
                % (i, len(todo), el / 60, len(fails), el / i * (len(todo) - i) / 60))
        time.sleep(0.12)
    log("[다음] 완료 %d개, 실패 %d개  총 %.1f분"
        % (len(todo) - len(fails), len(fails), (time.time() - t0) / 60))
    if fails:
        log("  실패 목록(앞 20개): %s" % fails[:20])
    return fails


def run_naver(tickers):
    os.makedirs(C.NAVER_DIR, exist_ok=True)
    todo = [t for t in tickers if not os.path.exists(
        os.path.join(C.NAVER_DIR, "%s.csv" % t))]
    log("[네이버] 대상 %d개 (캐시 %d개 건너뜀)" % (len(todo), len(tickers) - len(todo)))
    t0, fails = time.time(), []
    end = C.TEST_END.replace("-", "")
    for i, code in enumerate(todo, 1):
        df = fetch_naver(code, C.DATA_START, end)
        if df is None or df.empty:
            fails.append(code)
        else:
            df.to_csv(os.path.join(C.NAVER_DIR, "%s.csv" % code), index=False)
        if i % 100 == 0:
            el = time.time() - t0
            log("  %4d/%d  %.1f분 경과  실패 %d  (잔여 약 %.1f분)"
                % (i, len(todo), el / 60, len(fails), el / i * (len(todo) - i) / 60))
        time.sleep(0.12)
    log("[네이버] 완료 %d개, 실패 %d개  총 %.1f분"
        % (len(todo) - len(fails), len(fails), (time.time() - t0) / 60))
    return fails


def run_index():
    """RS 벤치마크용 코스피/코스닥 지수 일봉. 네이버 siseJson은 종목뿐 아니라
    지수 심볼(KOSPI/KOSDAQ)도 동일 포맷으로 반환한다."""
    os.makedirs(C.INDEX_DIR, exist_ok=True)
    end = C.TEST_END.replace("-", "")
    for sym in C.MARKET_INDEX.values():
        p = os.path.join(C.INDEX_DIR, "%s.csv" % sym)
        if os.path.exists(p):
            log("[지수] %s 캐시 사용" % sym)
            continue
        df = fetch_naver(sym, C.DATA_START, end)
        if df is None or df.empty:
            log("[지수] %s 수집 실패" % sym)
            continue
        df.to_csv(p, index=False)
        log("[지수] %s 저장 완료 (%d행)" % (sym, len(df)))


def main():
    os.makedirs(C.DATA, exist_ok=True)
    lst_path = os.path.join(C.DATA, "tickers.csv")
    if os.path.exists(lst_path):
        tickers = pd.read_csv(lst_path, dtype={"code": str})
        log("[종목리스트] 캐시 사용: %d개" % len(tickers))
    else:
        tickers = fetch_ticker_list()
        tickers.to_csv(lst_path, index=False)
    run_daum(tickers["code"].tolist())
    run_index()


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- 투자자별 순매매
def fetch_investor_page(session, code, page, retries=3):
    """네이버 '외국인·기관' 페이지 한 장(20거래일)의 순매매 표를 파싱한다."""
    import io as _io
    url = "https://finance.naver.com/item/frgn.naver"
    for attempt in range(retries):
        try:
            r = session.get(url, params={"code": code, "page": page}, timeout=20)
            if r.status_code != 200:
                time.sleep(1.0 + attempt)
                continue
            r.encoding = "euc-kr"
            for t in pd.read_html(_io.StringIO(r.text)):
                cols = t.columns
                if not isinstance(cols, pd.MultiIndex):
                    continue
                if "기관" not in [c[0] for c in cols]:
                    continue
                t = t.dropna(how="all")
                t.columns = ["date", "close", "chg", "rate", "volume",
                             "inst_net", "frgn_net", "frgn_shares", "frgn_ratio"]
                t = t.dropna(subset=["date"])
                t = t[t["date"].astype(str).str.match(r"\d{4}\.\d{2}\.\d{2}$")]
                return t[["date", "inst_net", "frgn_net"]]
            return None
        except Exception:
            time.sleep(1.0 + attempt)
    return None


def run_investor(tickers, max_pages=145):
    """종목별 기관·외국인 순매매를 DATA_START 까지 거슬러 수집.

    페이지당 20거래일이라 10년치는 종목당 약 130페이지가 필요하다.
    이미 받은 종목은 건너뛴다(원천 데이터 영구 캐시 원칙).
    """
    os.makedirs(C.INVESTOR_DIR, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": "https://finance.naver.com/"})
    start = "%s.%s.%s" % (C.DATA_START[:4], C.DATA_START[4:6], C.DATA_START[6:])

    todo = [t for t in tickers if not os.path.exists(
        os.path.join(C.INVESTOR_DIR, "%s.csv" % t))]
    log("[투자자] 대상 %d개 (캐시 %d개 건너뜀)" % (len(todo), len(tickers) - len(todo)))
    t0, fails, pages = time.time(), [], 0

    for i, code in enumerate(todo, 1):
        rows = []
        for pg in range(1, max_pages + 1):
            t = fetch_investor_page(s, code, pg)
            pages += 1
            if t is None or len(t) == 0:
                break
            rows.append(t)
            if str(t["date"].iloc[-1]) <= start:   # DATA_START 이전까지 받았으면 중단
                break
            time.sleep(0.1)
        if not rows:
            fails.append(code)
        else:
            df = pd.concat(rows, ignore_index=True).drop_duplicates(subset=["date"])
            df["date"] = pd.to_datetime(df["date"], format="%Y.%m.%d")
            df = df[df["date"] >= pd.Timestamp(C.DATA_START)].sort_values("date")
            df.to_csv(os.path.join(C.INVESTOR_DIR, "%s.csv" % code), index=False)
        if i % 20 == 0:
            el = time.time() - t0
            log("  %4d/%d  %.1f분 경과  페이지 %d  실패 %d  (잔여 약 %.1f분)"
                % (i, len(todo), el / 60, pages, len(fails), el / i * (len(todo) - i) / 60))
    log("[투자자] 완료 %d개, 실패 %d개, 총 %d페이지  %.1f분"
        % (len(todo) - len(fails), len(fails), pages, (time.time() - t0) / 60))
    return fails
