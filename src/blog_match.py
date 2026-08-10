# -*- coding: utf-8 -*-
"""블로그 매매와의 일치율 측정.

외부 블로그(깡토)가 공개한 '최근 4년 수익률 상위 10개 매매' 목록을 기준점으로 삼아,
현재 설정이 **같은 종목을 같은 날 사고 파는가**를 잰다. 성과(CAGR/MDD)와는 별개의
지표이며, 규칙을 블로그 쪽으로 수렴시키는 작업의 진척도를 본다.

각 종목이 어느 단계에서 막혔는지까지 보여준다:
    유니버스(시점) -> 시장필터 -> 시그널 -> 진입 -> 청산일

사용:
    python src/blog_match.py            # output/trades.csv 기준, 시그널까지 진단
    python src/blog_match.py --quick    # 진입 일치만 (패널 재계산 없이 빠르게)
"""
import os
import pickle
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

# (종목명, 진입일, 청산일, 수익률%) — 블로그 공개 상위 10개
BLOG = [
    ("대우건설",         "2026-02-10", "2026-05-12", 343.83),
    ("원익홀딩스",       "2025-08-25", "2025-11-17", 296.86),
    ("에코프로",         "2023-02-07", "2023-05-08", 295.44),
    ("삼성전기",         "2026-04-08", "2026-07-02", 279.24),
    ("셀바스AI",         "2023-01-09", "2023-03-03", 264.04),
    ("에스티큐브",       "2022-07-07", "2022-08-30", 192.35),
    ("금양",             "2022-07-22", "2022-09-29", 191.67),
    ("실리콘투",         "2024-05-09", "2024-06-28", 188.96),
    ("씨어스",           "2025-08-22", "2025-12-05", 177.12),
    ("HLB바이오스텝",    "2022-05-11", "2022-06-17", 150.65),
]


def _name_col(tk):
    for c in ("name", "종목명"):
        if c in tk.columns:
            return c
    raise KeyError("tickers.csv 에 종목명 컬럼이 없다")


def measure(quick=False, verbose=True):
    tk = pd.read_csv(os.path.join(C.DATA, "tickers.csv"), dtype=str)
    nc = _name_col(tk)
    name2code = dict(zip(tk[nc], tk["code"]))
    tr = pd.read_csv(os.path.join(C.OUT, "trades.csv"),
                     parse_dates=["entry_date", "exit_date"])

    uni = None
    upath = os.path.join(C.DATA, "universe.pkl")
    if os.path.exists(upath):
        with open(upath, "rb") as f:
            cached = pickle.load(f)
        uni = cached["uni"] if isinstance(cached, dict) and "uni" in cached else cached

    sigset, openmap, dmap = {}, {}, {}
    if not quick:
        import run as RUN
        codes = open(os.path.join(C.DATA, "universe_codes.txt")).read().split()
        panels, days, sig, _, mmap, mopen, _ = RUN.build_panels(codes, verbose=False)
        dmap = {d.strftime("%Y-%m-%d"): i for i, d in enumerate(days)}
        sigset = {i: set(cs) for i, cs in sig.items()}
        openmap = (mmap, mopen)

    rows, hit_in, hit_out = [], 0, 0
    for nm, ed, xd, ret in BLOG:
        code = name2code.get(nm)
        di = dmap.get(ed)

        in_uni = "?"
        if uni is not None and code:
            in_uni = "O" if code in uni.get(ed[:7], set()) else "X"

        # 시장필터가 꺼져 있으면 '해당없음' — 통과로 센다
        mkt = "-" if not C.MARKET_FILTER else "?"
        if C.MARKET_FILTER and openmap and code:
            mm, mo = openmap
            sym = mm.get(code) if isinstance(mm, dict) else None
            # 패널에 없는 종목(유니버스 밖)은 판정 불가 — 'O' 로 오표시하면 안 된다
            if sym and mo and sym in mo and di is not None:
                mkt = "O" if mo[sym][di] else "X"

        sg = "?" if quick or di is None else ("O" if code in sigset.get(di, set()) else "X")

        m = tr[(tr["name"] == nm) & (tr["entry_date"] == pd.Timestamp(ed))]
        entered = len(m) > 0
        exit_ok = ""
        if entered:
            hit_in += 1
            got = m.iloc[0]["exit_date"]
            gap = abs((got - pd.Timestamp(xd)).days)
            if gap <= 1:
                hit_out += 1
            exit_ok = "%s (%+d일)" % (got.date(), (got - pd.Timestamp(xd)).days)
        rows.append((nm, ed, in_uni, mkt, sg, "O" if entered else "X", exit_ok, ret))

    if verbose:
        print("\n=== 블로그 매매 일치율 ===")
        print("{:<16}{:<12}{:>5}{:>6}{:>6}{:>6}  {:<20}{:>9}".format(
            "종목", "블로그 진입", "유니버스", "시장", "시그널", "진입", "우리 청산일", "블로그"))
        print("-" * 92)
        for nm, ed, u, mk, sg, en, xo, ret in rows:
            print("{:<16}{:<12}{:>5}{:>6}{:>6}{:>6}  {:<20}{:>8.0f}%".format(
                nm, ed, u, mk, sg, en, xo or "-", ret))
        print("-" * 92)
        n = lambda i: sum(1 for r in rows if r[i] in ("O", "-"))
        print("  단계별 통과   유니버스 {}/10  ->  시장필터 {}/10  ->  시그널 {}/10"
              "  ->  진입 {}/10  ->  청산±1일 {}/10".format(
                  n(2), n(3), n(4), hit_in, hit_out))
        print("  ※ 진입은 슬롯 8개 + RS 우선순위 경쟁을 통과해야 하므로,"
              " 조건 개선의 진척은 '시그널' 칸으로 본다.")
    return hit_in, hit_out, rows


if __name__ == "__main__":
    measure(quick="--quick" in sys.argv)
