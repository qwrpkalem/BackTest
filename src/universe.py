# -*- coding: utf-8 -*-
"""시점별(point-in-time) 유니버스 구성.

'현재 시총 1조 이상'으로 필터하면 지난 10년간 크게 성장한 종목만 미리
골라놓고 백테스트하는 꼴이 되므로(look-ahead), 매월 말 시점의 실제
시가총액으로 매달 유니버스를 다시 만든다.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C


def filter_signature():
    """유니버스 필터에 영향을 주는 config 값 서명 — 캐시(universe.pkl) 유효성 검사용.

    이 값이 바뀌면 캐시가 낡은 필터 기준으로 만들어진 것이므로 재계산해야 한다.
    """
    return {"MIN_PRICE": C.MIN_PRICE, "MIN_LISTED_DAYS": C.MIN_LISTED_DAYS}


def build_universe(codes, verbose=True):
    """월말 기준 유니버스 dict: {'YYYY-MM': set(codes)}

    조건: 원주가 종가 >= 1,000원, 상장 250거래일 이상
    해당 월말 기준을 통과하면 '다음 달' 한 달간 매수 대상이 된다.
    """
    rows = []
    for i, code in enumerate(codes):
        p = os.path.join(C.DAUM_DIR, "%s.csv" % code)
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, parse_dates=["date"])
        d = d[d["close_r"] > 0]
        if len(d) < C.MIN_LISTED_DAYS:
            continue
        d = d.sort_values("date").reset_index(drop=True)
        d["bars"] = range(len(d))
        d["ym"] = d["date"].dt.to_period("M")
        last = d.groupby("ym").tail(1)          # 각 월의 마지막 거래일
        last = last[(last["close_r"] >= C.MIN_PRICE)
                    & (last["bars"] >= C.MIN_LISTED_DAYS)]
        for ym in last["ym"]:
            rows.append((str(ym), code))
        if verbose and (i + 1) % 500 == 0:
            print("  유니버스 스캔 %d/%d" % (i + 1, len(codes)), flush=True)

    df = pd.DataFrame(rows, columns=["ym", "code"])
    uni = {}
    for ym, g in df.groupby("ym"):
        # 해당 월말 통과 -> 다음 달에 적용
        nxt = (pd.Period(ym, "M") + 1)
        uni[str(nxt)] = set(g["code"])
    return uni


def summarize(uni):
    ks = sorted(uni.keys())
    s = pd.Series({k: len(uni[k]) for k in ks})
    return s
