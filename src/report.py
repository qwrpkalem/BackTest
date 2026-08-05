# -*- coding: utf-8 -*-
"""연도별 성과 리포트 — §7-1 정의에 따름."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C


def max_drawdown(equity):
    """일별 자산곡선 기준 최대 낙폭 (음수 반환)."""
    if len(equity) == 0:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def yearly_table(eq, tr):
    """연도 / 거래횟수 / 연수익률 / 승률 / 평균수익 / 평균손실 / 손익비 / MDD"""
    eq = eq.copy()
    eq.index = pd.to_datetime(eq.index)
    rows = []

    years = sorted(eq.index.year.unique())
    prev_end = float(C.INITIAL_CAPITAL)

    tr = tr.copy()
    if len(tr):
        tr["exit_date"] = pd.to_datetime(tr["exit_date"])
        tr["year"] = tr["exit_date"].dt.year

    for y in years:
        ye = eq[eq.index.year == y]["equity"]
        end_val = float(ye.iloc[-1])
        yret = end_val / prev_end - 1.0

        t = tr[tr["year"] == y] if len(tr) else tr
        n = len(t)
        if n:
            wins = t[t["ret"] > 0]["ret"]
            losses = t[t["ret"] <= 0]["ret"]
            win_rate = len(wins) / float(n)
            avg_w = float(wins.mean()) if len(wins) else np.nan
            avg_l = float(losses.mean()) if len(losses) else np.nan
            pr = (avg_w / abs(avg_l)) if (len(wins) and len(losses) and avg_l != 0) else np.nan
        else:
            win_rate = avg_w = avg_l = pr = np.nan

        rows.append({
            "연도": y, "거래횟수": n, "연수익률": yret, "승률": win_rate,
            "평균 수익": avg_w, "평균 손실": avg_l, "손익비": pr,
            "MDD": max_drawdown(ye),
        })
        prev_end = end_val

    # ---- 전체 행 ----
    total_n = len(tr)
    if total_n:
        wins = tr[tr["ret"] > 0]["ret"]
        losses = tr[tr["ret"] <= 0]["ret"]
        win_rate = len(wins) / float(total_n)
        avg_w = float(wins.mean()) if len(wins) else np.nan
        avg_l = float(losses.mean()) if len(losses) else np.nan
        pr = (avg_w / abs(avg_l)) if (len(wins) and len(losses) and avg_l != 0) else np.nan
    else:
        win_rate = avg_w = avg_l = pr = np.nan

    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    final = float(eq["equity"].iloc[-1])
    cagr = (final / float(C.INITIAL_CAPITAL)) ** (1.0 / yrs) - 1.0 if yrs > 0 else np.nan

    rows.append({
        "연도": "전체", "거래횟수": total_n, "연수익률": cagr, "승률": win_rate,
        "평균 수익": avg_w, "평균 손실": avg_l, "손익비": pr,
        "MDD": max_drawdown(eq["equity"]),
    })
    return pd.DataFrame(rows)


def fmt_table(df):
    def pct(x):
        return "-" if pd.isna(x) else "%+.2f%%" % (x * 100)

    def pct0(x):
        return "-" if pd.isna(x) else "%.1f%%" % (x * 100)

    def rat(x):
        return "-" if pd.isna(x) else "%.2f" % x

    out = pd.DataFrame({
        "연도": df["연도"].astype(str),
        "거래횟수": df["거래횟수"].astype(int),
        "연수익률": df["연수익률"].map(pct),
        "승률": df["승률"].map(pct0),
        "평균 수익": df["평균 수익"].map(pct),
        "평균 손실": df["평균 손실"].map(pct),
        "손익비": df["손익비"].map(rat),
        "MDD": df["MDD"].map(pct),
    })
    out.loc[out.index[-1], "연수익률"] = out.loc[out.index[-1], "연수익률"] + " (CAGR)"
    return out


def to_markdown(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def reason_stats(tr):
    if not len(tr):
        return pd.DataFrame()
    g = tr.groupby("reason").agg(
        건수=("ret", "size"), 비중=("ret", lambda s: len(s)),
        평균수익률=("ret", "mean"), 총손익=("pnl", "sum"))
    g["비중"] = (g["건수"] / len(tr) * 100).round(1).astype(str) + "%"
    g["평균수익률"] = (g["평균수익률"] * 100).round(2).astype(str) + "%"
    g["총손익"] = (g["총손익"] / 1e6).round(1).astype(str) + "백만"
    return g.sort_values("건수", ascending=False)


def r_stats(tr):
    """v4: 진입 R 구간별 성과 — 사이징이 실제로 성과와 연결됐는지 확인용."""
    if not len(tr) or "entry_r" not in tr.columns:
        return pd.DataFrame()
    g = tr.groupby("entry_r").agg(
        건수=("ret", "size"),
        평균수익률=("ret", "mean"),
        성공률=("success", "mean"),
        총손익=("pnl", "sum"))
    g["비중"] = (g["건수"] / len(tr) * 100).round(1).astype(str) + "%"
    g["평균수익률"] = (g["평균수익률"] * 100).round(2).astype(str) + "%"
    g["성공률"] = (g["성공률"] * 100).round(1).astype(str) + "%"
    g["총손익"] = (g["총손익"] / 1e6).round(1).astype(str) + "백만"
    g.index.name = "진입R"
    return g[["건수", "비중", "성공률", "평균수익률", "총손익"]]


def regime_stats(tr):
    """v4: 시장 국면별 성과."""
    if not len(tr) or "regime_r" not in tr.columns:
        return pd.DataFrame()
    name = {1: "약세(1R)", 2: "횡보(2R)", 3: "강세(3R)"}
    t = tr.copy()
    t["국면"] = t["regime_r"].map(name)
    g = t.groupby("국면").agg(
        건수=("ret", "size"),
        평균수익률=("ret", "mean"),
        성공률=("success", "mean"),
        총손익=("pnl", "sum"))
    g["비중"] = (g["건수"] / len(t) * 100).round(1).astype(str) + "%"
    g["평균수익률"] = (g["평균수익률"] * 100).round(2).astype(str) + "%"
    g["성공률"] = (g["성공률"] * 100).round(1).astype(str) + "%"
    g["총손익"] = (g["총손익"] / 1e6).round(1).astype(str) + "백만"
    return g[["건수", "비중", "성공률", "평균수익률", "총손익"]]


def save_equity_plot(eq, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
        e = eq["equity"] / 1e8
        ax[0].plot(eq.index, e, lw=1.2, color="#2563eb")
        ax[0].set_ylabel("Equity (100M KRW)")
        ax[0].grid(alpha=0.3)
        ax[0].set_title("Equity Curve")

        dd = (eq["equity"] / eq["equity"].cummax() - 1.0) * 100
        ax[1].fill_between(eq.index, dd, 0, color="#dc2626", alpha=0.5)
        ax[1].set_ylabel("Drawdown (%)")
        ax[1].grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(path, dpi=110)
        plt.close(fig)
        return True
    except Exception as e:
        print("  (그래프 생성 실패: %s)" % e)
        return False
