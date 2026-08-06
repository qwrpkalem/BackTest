# -*- coding: utf-8 -*-
"""기간 분할 검증 (In-Sample / Out-of-Sample)

앞 구간에서 파라미터를 고르고 뒤 구간에서 그 선택이 통하는지 확인한다.
각 구간은 초기자본 1억으로 독립 시작한다.

    python src/validate_split.py

전체 기간으로 파라미터를 고르면 그 기간에만 맞는 값을 뽑게 된다(과최적화).
IS 순위와 OOS 순위의 상관(rho)이 0 근처면, 앞 구간에서 좋았던 값이 뒤 구간에서
좋을 이유가 없다는 뜻이므로 그 파라미터는 튜닝해도 소용이 없다.

현재는 시장폭(breadth) 임계값을 대상으로 한다. 다른 파라미터를 검증하려면
GRID 와 run() 안의 국면 계산 부분을 바꾸면 된다.
"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import engine
import report as REP
import run as RUN

IS_START, IS_END = "2016-01-04", "2021-12-31"
OS_START, OS_END = "2022-01-01", "2026-07-31"

GRID = [(b, r) for b in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55)
        for r in (0.60, 0.65, 0.70, 0.75, 0.80) if b < r]


def spearman(a, b):
    """순위상관 = 순위에 대한 Pearson (scipy 없이 계산)."""
    return pd.Series(a).rank().corr(pd.Series(b).rank())


def main():
    with open(os.path.join(C.DATA, "universe.pkl"), "rb") as f:
        cached = pickle.load(f)
    uni = cached["uni"] if isinstance(cached, dict) and "uni" in cached else cached
    codes = open(os.path.join(C.DATA, "universe_codes.txt")).read().split()
    panels, days, sig, _, mmap, mopen, ratio = RUN.build_panels(codes, verbose=False)
    if ratio is None:
        raise SystemExit("REGIME_MODE='breadth' 에서만 쓸 수 있습니다.")

    def slice_period(start, end):
        """기간을 잘라 엔진 입력을 만든다 (numpy 슬라이스는 view 라 복사 비용 없음)."""
        idx = np.flatnonzero((days >= start) & (days <= end))
        a, b = idx[0], idx[-1] + 1
        return (
            {c: {k: v[a:b] for k, v in p.items()} for c, p in panels.items()},
            days[a:b],
            {di - a: cs for di, cs in sig.items() if a <= di < b},
            {k: v[a:b] for k, v in mopen.items()} if mopen else None,
            ratio[a:b],
        )

    seg = {"IS": slice_period(IS_START, IS_END),
           "OOS": slice_period(OS_START, OS_END)}

    def run(name, bull, bear):
        p2, d2, s2, m2, r2 = seg[name]
        reg = np.full(len(d2), float(C.REGIME_SIDE))
        reg[r2 < bull] = float(C.REGIME_BULL)
        reg[r2 > bear] = float(C.REGIME_BEAR)
        reg[np.isnan(r2)] = float(C.REGIME_SIDE)
        bt = engine.Backtest(p2, uni, d2, s2,
                             regime_by_index={s: reg for s in C.MARKET_INDEX.values()},
                             market_of=mmap, market_open=m2)
        eq, tr = bt.run(verbose=False)
        yrs = (eq.index[-1] - eq.index[0]).days / 365.25
        cagr = (eq["equity"].iloc[-1] / C.INITIAL_CAPITAL) ** (1 / yrs) - 1
        mdd = REP.max_drawdown(eq["equity"])
        return cagr, mdd, cagr / abs(mdd)

    rows = []
    for bull, bear in GRID:
        ic, im, ir = run("IS", bull, bear)
        oc, om, orr = run("OOS", bull, bear)
        rows.append(dict(bull=bull, bear=bear, is_cagr=ic, is_mdd=im, is_r=ir,
                         os_cagr=oc, os_mdd=om, os_r=orr))
    d = pd.DataFrame(rows)

    print("\n" + "=" * 86)
    print("기간 분할 검증 — IS(%s~%s) 로 고르고 OOS(%s~%s) 로 검증"
          % (IS_START[:4], IS_END[:4], OS_START[:4], OS_END[:4]))
    print("=" * 86)
    print("{:>6} {:>6} | {:>9} {:>9} {:>8} | {:>9} {:>9} {:>8}".format(
        "강세<", "하락>", "IS CAGR", "IS MDD", "IS비율", "OOS CAGR", "OOS MDD", "OOS비율"))
    for r in d.itertuples():
        cur = (abs(r.bull - C.BREADTH_BULL_MAX) < 1e-9
               and abs(r.bear - C.BREADTH_BEAR_MIN) < 1e-9)
        print("{:>5.0f}% {:>5.0f}% | {:>8.2f}% {:>8.2f}% {:>8.3f} | {:>8.2f}% {:>8.2f}% {:>8.3f}{}".format(
            r.bull * 100, r.bear * 100, r.is_cagr * 100, r.is_mdd * 100, r.is_r,
            r.os_cagr * 100, r.os_mdd * 100, r.os_r, "  <- 현재 설정" if cur else ""))

    print("\n=== IS 상위 5개가 OOS 에서는? ===")
    for r in d.nlargest(5, "is_r").itertuples():
        print("  강세<{:.0f}% 하락>{:.0f}%  IS {}위 (비율 {:.3f})  ->  OOS {}/{}위 (비율 {:.3f})".format(
            r.bull * 100, r.bear * 100, int((d["is_r"] > r.is_r).sum()) + 1, r.is_r,
            int((d["os_r"] > r.os_r).sum()) + 1, len(d), r.os_r))

    print("\n=== IS 성적이 OOS 성적을 예측하는가 ===")
    print("  CAGR/|MDD| 순위상관 rho = %+.3f" % spearman(d["is_r"], d["os_r"]))
    print("  CAGR       순위상관 rho = %+.3f" % spearman(d["is_cagr"], d["os_cagr"]))
    print("  rho 가 0 근처면 IS 에서 좋았던 값이 OOS 에서 좋을 이유가 없다는 뜻")

    print("\n=== 전략 자체의 견고성 ===")
    print("  IS  CAGR %+.2f%% ~ %+.2f%% (중앙 %+.2f%%)"
          % (d["is_cagr"].min() * 100, d["is_cagr"].max() * 100, d["is_cagr"].median() * 100))
    print("  OOS CAGR %+.2f%% ~ %+.2f%% (중앙 %+.2f%%)"
          % (d["os_cagr"].min() * 100, d["os_cagr"].max() * 100, d["os_cagr"].median() * 100))
    print("  두 구간 모두 플러스인 조합: %d/%d"
          % (((d["is_cagr"] > 0) & (d["os_cagr"] > 0)).sum(), len(d)))


if __name__ == "__main__":
    main()
