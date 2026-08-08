# -*- coding: utf-8 -*-
"""채택 버전 표시 — 폴더만 봐도 지금 무엇이 쓰이는지 알 수 있게 한다.

파일 '이름'에 버전이 들어가므로 열어보지 않아도 탐색기에서 바로 보인다.
  d:/BackTest/_현재버전_v26.md            <- 저장소 최상단
  d:/BackTest/output/history/_현재_v26.md <- 버전 폴더들 사이

사용:
    python src/set_current.py v26 "RS 우선순위"
"""
import io
import os
import re
import sys

import config as C

ROOT = C.ROOT
HIST = os.path.join(C.OUT, "history")


def _clear(dirpath, pattern):
    """이전 마커 제거 — 버전이 두 개로 보이는 일이 없도록."""
    if not os.path.isdir(dirpath):
        return
    for fn in os.listdir(dirpath):
        if re.match(pattern, fn):
            os.remove(os.path.join(dirpath, fn))


def _metrics():
    """output/ 의 현재 산출물에서 성과 요약을 읽는다."""
    import pandas as pd

    tr = pd.read_csv(os.path.join(C.OUT, "trades.csv"))
    eq = pd.read_csv(os.path.join(C.OUT, "equity.csv"), parse_dates=["date"])
    e = eq["equity"]
    yrs = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days / 365.25
    cagr = (e.iloc[-1] / C.INITIAL_CAPITAL) ** (1 / yrs) - 1
    mdd = (e / e.cummax() - 1).min()
    return {
        "거래": len(tr),
        "CAGR": cagr,
        "MDD": mdd,
        "승률": (tr["ret"] > 0).mean(),
        "최종자산": e.iloc[-1],
    }


def main(ver, note=""):
    m = _metrics()
    body = (
        "# 현재 채택 버전 — **" + ver + "**\n\n"
        + ("> " + note + "\n\n" if note else "")
        + "`src/config.py` 와 `output/` 은 지금 이 버전 상태입니다.\n\n"
        + "| 항목 | 값 |\n|---|---|\n"
        + "| 전략명 | " + C.STRATEGY_NAME + " |\n"
        + "| 기간 | " + C.TEST_START + " ~ " + C.TEST_END + " |\n"
        + "| 거래 | {:,}건 |\n".format(m["거래"])
        + "| CAGR | **{:+.2f}%** |\n".format(m["CAGR"] * 100)
        + "| MDD | {:.2f}% |\n".format(m["MDD"] * 100)
        + "| 승률 | {:.1f}% |\n".format(m["승률"] * 100)
        + "| 최종자산 | **{:,.0f}원** |\n".format(m["최종자산"])
        + "\n---\n\n"
        + "- 매매 규칙: [매매규칙.md](매매규칙.md)\n"
        + "- 전체 스펙: [backtest_spec.md](backtest_spec.md)\n"
        + "- 버전별 이력: [output/CHANGELOG.md](output/CHANGELOG.md)\n"
        + "- 이 버전의 보관본: [output/history/" + ver + "/](output/history/" + ver + "/)\n"
    )
    _clear(ROOT, r"_현재버전_.*\.md$")
    io.open(os.path.join(ROOT, "_현재버전_" + ver + ".md"), "w", encoding="utf-8").write(body)

    _clear(HIST, r"_현재_.*\.md$")
    io.open(os.path.join(HIST, "_현재_" + ver + ".md"), "w", encoding="utf-8").write(
        "# 현재 채택 = **" + ver + "**\n\n"
        + "CAGR {:+.2f}% / MDD {:.2f}% / 최종 {:,.0f}원\n\n".format(
            m["CAGR"] * 100, m["MDD"] * 100, m["최종자산"])
        + "나머지 폴더는 검증만 하고 기각한 버전입니다. "
        + "[전체 비교표](README.md) · [변경 이력](../CHANGELOG.md)\n"
    )

    # 매매규칙.md 제목줄의 버전도 함께 맞춘다 (두 곳이 어긋나지 않도록)
    rp = os.path.join(ROOT, "매매규칙.md")
    if os.path.exists(rp):
        s = io.open(rp, encoding="utf-8").read()
        s2 = re.sub(r"^(# 매매 규칙 — 52주 신고가 모멘텀 )\(v\d+\)",
                    r"\1(" + ver + ")", s, count=1, flags=re.M)
        if s2 != s:
            io.open(rp, "w", encoding="utf-8").write(s2)

    print("[현재버전] %s — CAGR %+.2f%% / MDD %.2f%% / 최종 %,.0f원"
          .replace("%,", "%") % (ver, m["CAGR"] * 100, m["MDD"] * 100, m["최종자산"]))
    print("  ->  _현재버전_%s.md  /  output/history/_현재_%s.md" % (ver, ver))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python src/set_current.py v26 [메모]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
