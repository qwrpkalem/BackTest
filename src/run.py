# -*- coding: utf-8 -*-
"""3단계: 패널 구성 -> 백테스트 실행 -> 리포트 출력."""
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import engine
import indicators as IND
import report as REP


def _load_market_map():
    """code -> 벤치마크 지수명(KOSPI/KOSDAQ) 매핑 (tickers.csv의 market_code 기준)."""
    t = pd.read_csv(os.path.join(C.DATA, "tickers.csv"), dtype={"code": str})
    return {row.code: C.MARKET_INDEX.get(row.market_code)
            for row in t.itertuples()}


def _load_index_frames():
    """RS 벤치마크용 지수(KOSPI/KOSDAQ) rs_raw 시리즈."""
    out = {}
    for sym in C.MARKET_INDEX.values():
        p = os.path.join(C.INDEX_DIR, "%s.csv" % sym)
        df = IND.build_index(p)
        if df is None:
            print("[경고] 지수 데이터 없음: %s (RS 필터가 비활성화됩니다. "
                  "src/fetch.py 의 run_index()를 먼저 실행하세요)" % sym, flush=True)
        out[sym] = df
    return out


def _trading_calendar():
    """KRX 거래일 달력. 코스피 지수 파일의 날짜가 개별 종목 거래일의
    상위집합이므로(휴장일에는 지수도 산출되지 않음) 이를 공통 달력으로 쓴다."""
    d = pd.read_csv(os.path.join(C.INDEX_DIR, "KOSPI.csv"), parse_dates=["date"])
    days = pd.DatetimeIndex(sorted(d["date"].unique()))
    return days[(days >= C.TEST_START) & (days <= C.TEST_END)]


def build_panels(codes, verbose=True):
    """공통 거래일 캘린더에 정렬된 종목별 배열 패널 생성.

    메모리 주의: 종목별 DataFrame을 모두 들고 있으면 32bit 파이썬 주소공간
    (2GB)을 넘겨 스래싱/MemoryError가 난다(2,476종목 x 2,842행 x 19컬럼 =
    약 1.1GB). 따라서 한 종목씩 즉시 배열로 압축하고 DataFrame은 버린다.
    또한 엔진은 시그널이 난 종목만 매수하므로, 시그널이 한 번도 없는 종목은
    패널에 담지 않는다.
    """
    days = _trading_calendar()
    market_map = _load_market_map()
    index_frames = _load_index_frames()
    # 종목 RS 백분위 >= 지수 RS 백분위는, 같은 날 cross-section에서 백분위가
    # raw score의 순서를 그대로 보존하는 단조 변환이므로 (동점이 아닌 한)
    # "종목 raw score >= 지수 raw score" 비교와 결과가 동일하다.
    index_rs = {sym: (df.set_index("date")["rs_raw"].reindex(days) if df is not None else None)
                for sym, df in index_frames.items()}
    rs_enabled = all(v is not None for v in index_rs.values())
    if not rs_enabled:
        print("[경고] 지수 데이터가 없어 RS 필터가 적용되지 않습니다.", flush=True)

    n_flow_before = n_flow_after = 0
    panels, signal_by_day = {}, {}
    # v12: 시장폭(breadth) 집계 — 종가가 200일선 아래인 종목 수 / 유효 종목 수
    below = np.zeros(len(days))
    valid_cnt = np.zeros(len(days))
    n_data, t0 = 0, time.time()
    for i, code in enumerate(codes, 1):
        df = IND.build(code)
        if df is None:
            continue
        n_data += 1
        d = df.set_index("date").reindex(days)
        del df

        sb = d["sma_breadth"].values
        cl = d["close"].values
        ok = ~(np.isnan(sb) | np.isnan(cl))
        valid_cnt += ok
        below += ok & (cl < sb)

        base = d["signal_base"].fillna(False).values.astype(bool)
        bench_series = index_rs.get(market_map.get(code))
        if rs_enabled and bench_series is not None:
            rs_ok = (d["rs_raw"] >= bench_series).fillna(False).values
        else:
            rs_ok = np.ones(len(days), dtype=bool)   # RS 데이터 없으면 필터 미적용
        # v16~v18: 투자자 매수 연속성 (최근 N일 중 M일 이상 순매수)
        if C.INST_FILTER:
            ipath = os.path.join(C.INVESTOR_DIR, "%s.csv" % code)
            if os.path.exists(ipath):
                iv = (pd.read_csv(ipath, parse_dates=["date"])
                        .set_index("date").reindex(days))
                cnt_i = (iv["inst_total"] > 0).rolling(C.INST_WINDOW).sum()
                cnt_f = (iv["fin_invest"] > 0).rolling(C.INST_WINDOW).sum()
                ok_i = cnt_i >= C.INST_MIN_DAYS
                ok_f = cnt_f >= C.INST_MIN_DAYS
                flow_ok = {"inst": ok_i, "fin": ok_f}.get(C.INST_MODE, ok_i & ok_f)
                flow_ok = flow_ok.fillna(False).values
            else:
                flow_ok = np.zeros(len(days), dtype=bool)   # 데이터 없으면 진입 불가
        else:
            flow_ok = np.ones(len(days), dtype=bool)

        n_flow_before += int((base & rs_ok).sum())
        idx = np.flatnonzero(base & rs_ok & flow_ok)
        n_flow_after += int(idx.size)
        if idx.size == 0:
            continue                     # 매수 후보가 될 일이 없는 종목

        panels[code] = {
            "open": d["open"].values.astype(np.float64),
            "high": d["high"].values.astype(np.float64),
            "low": d["low"].values.astype(np.float64),
            "close": d["close"].values.astype(np.float64),
            "sma20": d["sma20"].values.astype(np.float64),
            "value": np.nan_to_num(d["value"].values.astype(np.float64)),
            "valid": d["close"].notna().values,
        }
        for di in idx:
            signal_by_day.setdefault(int(di), []).append(code)

        if verbose and i % 200 == 0:
            print("  지표 계산 %d/%d (%.1f분, 패널 %d종목)"
                  % (i, len(codes), (time.time() - t0) / 60, len(panels)), flush=True)

    if not panels:
        raise SystemExit("시그널이 발생한 종목이 없습니다.")

    # 시장 국면 (1~3R). 거래일 캘린더에 맞춰 배열로 만든다.
    regime_by_index = {}
    ratio = None
    if C.REGIME_MODE == "breadth":
        # v12: 종가가 200일선 아래인 종목 비율로 판정. 시장 전체 공통 값이므로
        # 두 지수 키에 같은 배열을 넣어 엔진 인터페이스를 그대로 쓴다.
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = np.where(valid_cnt > 0, below / valid_cnt, np.nan)
        reg = np.full(len(days), float(C.REGIME_SIDE))
        reg[ratio < C.BREADTH_BULL_MAX] = float(C.REGIME_BULL)
        reg[ratio > C.BREADTH_BEAR_MIN] = float(C.REGIME_BEAR)
        reg[np.isnan(ratio)] = float(C.REGIME_SIDE)     # 워밍업 구간
        for sym in C.MARKET_INDEX.values():
            regime_by_index[sym] = reg
        share = pd.Series(reg).value_counts(normalize=True)
        print("[국면] 시장폭 기준 (200일선 아래 비율) — 하락 %.0f%% / 횡보 %.0f%% / 강세 %.0f%%"
              % (share.get(float(C.REGIME_BEAR), 0) * 100,
                 share.get(float(C.REGIME_SIDE), 0) * 100,
                 share.get(float(C.REGIME_BULL), 0) * 100), flush=True)
        v = ratio[~np.isnan(ratio)]
        print("[국면] 200일선 아래 비율: 중앙값 %.0f%% / 최소 %.0f%% / 최대 %.0f%% (대상 %d종목)"
              % (np.median(v) * 100, v.min() * 100, v.max() * 100, int(valid_cnt.max())), flush=True)
    else:
        for sym, df in index_frames.items():
            if df is not None:
                r = df.set_index("date")["regime"].reindex(days).fillna(C.REGIME_SIDE)
                regime_by_index[sym] = r.values.astype(np.float64)
                share = pd.Series(r.values).value_counts(normalize=True).sort_index()
                print("[국면] %-6s 약세 %.0f%% / 횡보 %.0f%% / 강세 %.0f%%"
                      % (sym, share.get(C.REGIME_BEAR, 0) * 100,
                         share.get(C.REGIME_SIDE, 0) * 100,
                         share.get(C.REGIME_BULL, 0) * 100), flush=True)

    # v12: 시장 필터 — 시장별로 다른 기준선. 해당 지수가 기준선 아래면 그 시장
    # 종목의 신규 진입만 막는다 (코스피 60일선 / 코스닥 120일선).
    market_open = None
    if C.MARKET_FILTER:
        market_open = {}
        for sym, ma_len in C.MARKET_FILTER_MA.items():
            p = os.path.join(C.INDEX_DIR, "%s.csv" % sym)
            mi = pd.read_csv(p, parse_dates=["date"]).sort_values("date").set_index("date")
            ma = mi["close"].rolling(ma_len).mean()
            ok = (mi["close"] >= ma).reindex(days).fillna(False).values.astype(bool)
            market_open[sym] = ok
            print("[시장필터] %-6s %3d일선 — 진입 허용 %d일 / 중단 %d일 (%.0f%% 중단)"
                  % (sym, ma_len, ok.sum(), (~ok).sum(), (~ok).mean() * 100), flush=True)

    if C.INST_FILTER and n_flow_before:
        print("[수급필터] %s 최근 %d일 중 %d일 이상 순매수 — %d건 -> %d건 (%.1f%% 차단)"
              % (C.INST_MODE, C.INST_WINDOW, C.INST_MIN_DAYS, n_flow_before, n_flow_after,
                 (1 - n_flow_after / n_flow_before) * 100), flush=True)

    total_sig = sum(len(v) for v in signal_by_day.values())
    print("[패널] 데이터 보유 %d종목 -> 시그널 발생 %d종목 / 거래일 %d일 (%s ~ %s)"
          % (n_data, len(panels), len(days), days[0].date(), days[-1].date()), flush=True)
    print("[패널] 전체 시그널 발생 건수: %d건 (시그널 발생일 %d일)"
          % (total_sig, len(signal_by_day)), flush=True)
    return panels, days, signal_by_day, regime_by_index, market_map, market_open, ratio


def main():
    os.makedirs(C.OUT, exist_ok=True)

    with open(os.path.join(C.DATA, "universe.pkl"), "rb") as f:
        cached = pickle.load(f)
    uni = cached["uni"] if isinstance(cached, dict) and "uni" in cached else cached
    codes = open(os.path.join(C.DATA, "universe_codes.txt")).read().split()
    print("[시작] 유니버스 후보 %d개" % len(codes), flush=True)

    t0 = time.time()
    panels, days, sig_by_day, regime_by_index, market_map, market_open, _ = build_panels(codes)
    print("[타이밍] build_panels 완료 (%.1fs)" % (time.time() - t0), flush=True)

    print("\n[백테스트] 실행", flush=True)
    t1 = time.time()
    bt = engine.Backtest(panels, uni, days, sig_by_day,
                         regime_by_index=regime_by_index, market_of=market_map,
                         market_open=market_open)
    eq, tr = bt.run()
    if C.MARKET_FILTER:
        print("[시장필터] 필터로 차단된 시그널 %d건" % bt.blocked_signals, flush=True)
    print("[타이밍] bt.run() 완료 (%.1fs)" % (time.time() - t1), flush=True)

    # ---------------- 결과 저장 ----------------
    t2 = time.time()
    names = pd.read_csv(os.path.join(C.DATA, "tickers.csv"), dtype={"code": str})
    name_map = dict(zip(names["code"], names["name"]))
    if len(tr):
        tr.insert(1, "name", tr["code"].map(name_map))
        tr = tr.sort_values("exit_date")
        tr.to_csv(os.path.join(C.OUT, "trades.csv"), index=False, encoding="utf-8-sig")
    eq.to_csv(os.path.join(C.OUT, "equity.csv"), encoding="utf-8-sig")
    print("[타이밍] CSV 저장 완료 (%.1fs)" % (time.time() - t2), flush=True)

    t3 = time.time()
    tbl = REP.yearly_table(eq, tr)
    ftbl = REP.fmt_table(tbl)
    md = REP.to_markdown(ftbl)
    print("[타이밍] yearly_table 완료 (%.1fs)" % (time.time() - t3), flush=True)

    print("\n" + "=" * 78)
    print("연도별 성과")
    print("=" * 78)
    print(ftbl.to_string(index=False))

    t4 = time.time()
    rs = REP.reason_stats(tr)
    print("[타이밍] reason_stats 완료 (%.1fs)" % (time.time() - t4), flush=True)

    print("\n" + "=" * 78)
    print("청산 사유별 통계")
    print("=" * 78)
    print(rs.to_string())

    rst, gst, top = REP.r_stats(tr), REP.regime_stats(tr), REP.top_trades(tr, 10)
    print("\n" + "=" * 78)
    print("진입 R 구간별 성과")
    print("=" * 78)
    print(rst.to_string())
    print("\n" + "=" * 78)
    print("시장 국면별 성과")
    print("=" * 78)
    print(gst.to_string())

    print("\n" + "=" * 78)
    print("수익률 상위 10개 매매")
    print("=" * 78)
    print(top.to_string(index=False))

    t5 = time.time()
    ok = REP.save_equity_plot(eq, os.path.join(C.OUT, "equity_curve.png"))
    print("[타이밍] save_equity_plot 완료 (%.1fs)" % (time.time() - t5), flush=True)

    with open(os.path.join(C.OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("# 백테스트 결과 — %s\n\n" % C.STRATEGY_NAME)
        f.write("- 기간: %s ~ %s\n" % (days[0].date(), days[-1].date()))
        f.write("- 초기자본: {:,}원\n".format(C.INITIAL_CAPITAL))
        f.write("- 최종자산: {:,.0f}원\n\n".format(eq["equity"].iloc[-1]))
        f.write("## 연도별 성과\n\n" + md + "\n\n")
        f.write("## 청산 사유별 통계\n\n```\n")
        f.write(rs.to_string() + "\n```\n")
        if len(rst):
            f.write("\n## 진입 R 구간별 성과\n\n```\n" + rst.to_string() + "\n```\n")
        if len(gst):
            f.write("\n## 시장 국면별 성과\n\n```\n" + gst.to_string() + "\n```\n")
        if ok:
            f.write("\n## 자산 곡선\n\n![equity](equity_curve.png)\n")
        if len(top):
            f.write("\n## 수익률 상위 10개 매매\n\n"
                    + REP.to_markdown(top) + "\n")

    print("\n[저장] output/report.md, trades.csv, equity.csv, equity_curve.png")


if __name__ == "__main__":
    main()
