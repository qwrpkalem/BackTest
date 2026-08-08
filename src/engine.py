# -*- coding: utf-8 -*-
"""백테스트 엔진.

하루 처리 순서 (§4-2)
  1) 전일 20일선 이탈 예약분 -> 당일 시가 청산
  2) 갭하락(시가 <= S)       -> 시가 전량 청산
  3) 장중 터치(저가 <= S)    -> S 가격 전량 청산
  4) +24% 도달              -> 목표가에 30% 부분 익절 (포지션당 1회)
  5) 고점/스탑 갱신, 종가 < SMA20 이면 익일 청산 예약
  6) 종가에 신규 진입 (거래대금 큰 순, 빈 슬롯만큼)

모든 종목 배열은 공통 거래일 캘린더에 정렬되어 있어 di(일 인덱스)로 바로 접근한다.
"""
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C


class Position(object):
    __slots__ = ("code", "entry_date", "entry_px", "qty", "qty_init", "highest",
                 "stop", "tp_px", "partial_done", "pending_ma_exit",
                 "cost_total", "proceeds_total", "last_close",
                 "entry_r", "regime_r", "streak_r", "capped", "bear_exit")

    def __init__(self, code, date, px, qty, cost,
                 entry_r=0, regime_r=0, streak_r=0, capped=False):
        self.code = code
        self.entry_date = date
        self.entry_px = px
        self.qty = qty
        self.qty_init = qty
        self.highest = px
        self.stop = px * (1.0 - C.TRAIL_PCT)
        self.tp_px = px * (1.0 + C.PARTIAL_TP_PCT)
        self.partial_done = False
        self.pending_ma_exit = False
        self.cost_total = cost
        self.proceeds_total = 0.0
        self.last_close = px
        self.entry_r = entry_r            # v4: 진입 시 목표 R (시장국면 + 연속성)
        self.regime_r = regime_r
        self.streak_r = streak_r
        self.capped = capped              # 현금 부족으로 목표 R 을 못 채웠는가
        self.bear_exit = False            # v19: 고점권 대량 음봉으로 청산 예약됐는가


def sell_amount(price, qty):
    """매도 실수령액 — 슬리피지 + 수수료 + 거래세 차감."""
    return price * (1.0 - C.SLIPPAGE) * qty * (1.0 - C.FEE_SELL - C.TAX_SELL)


def buy_cost(price, qty):
    """매수 총지출 — 슬리피지 + 수수료 포함."""
    return price * (1.0 + C.SLIPPAGE) * qty * (1.0 + C.FEE_BUY)


class Backtest(object):
    def __init__(self, panels, universe, days, signal_by_day,
                 regime_by_index=None, market_of=None, market_open=None):
        self.panels = panels              # {code: {open,high,low,close,sma20,value,valid}}
        self.universe = universe          # {'YYYY-MM': set(code)}
        self.days = days                  # DatetimeIndex
        self.signal_by_day = signal_by_day  # {di: [code, ...]}
        self.regime_by_index = regime_by_index or {}   # {'KOSPI': ndarray(1~3), ...}
        self.market_of = market_of or {}               # {code: 'KOSPI'|'KOSDAQ'}
        # v12: 시장별 신규 진입 허용 여부 {'KOSPI': ndarray(bool), 'KOSDAQ': ...}.
        # None 이면 항상 허용. 해당 시장이 닫혀 있으면 그 시장 종목만 진입을 막는다.
        self.market_open = market_open
        self.blocked_signals = 0          # 시장 필터로 걸러진 시그널 수
        self.cash = float(C.INITIAL_CAPITAL)
        self.positions = {}
        self.trades = []
        self.equity = []
        # v4: 매매 성공 연속성 R. 1R 로 시작해 성공하면 +1R, 실패하면 -1R (1~3R)
        self.streak_r = C.R_MIN_UNITS
        self.streak_log = []              # (date, code, success, streak_r_after)
        # 손절선이 고점을 따라 올라가는지(트레일링) 여부에 따라 사유 코드가 다르다
        self._gap_reason = "TRAIL_GAP" if C.TRAILING_STOP else "STOP_GAP"
        self._intra_reason = "TRAIL_INTRA" if C.TRAILING_STOP else "STOP_INTRA"

    # ------------------------------------------------------------ 청산
    def _close_position(self, pos, date, reason):
        # v4 성공 판정: +24% 도달(부분익절 트리거) 여부만 본다. 24%에 못 닿았으면
        # 수익으로 끝났더라도 실패로 계산한다(이분법 — 스펙 §5-3).
        success = bool(pos.partial_done)
        self.trades.append({
            "code": pos.code,
            "entry_date": pos.entry_date,
            "exit_date": date,
            "entry_px": pos.entry_px,
            "qty": pos.qty_init,
            "cost": pos.cost_total,
            "proceeds": pos.proceeds_total,
            "pnl": pos.proceeds_total - pos.cost_total,
            "ret": (pos.proceeds_total - pos.cost_total) / pos.cost_total,
            "reason": reason,
            "partial_tp": pos.partial_done,
            "hold_days": (date - pos.entry_date).days,
            "entry_r": pos.entry_r,           # 진입 시 목표 R (2~6)
            "regime_r": pos.regime_r,         # 그중 시장국면 몫 (1~3)
            "streak_r": pos.streak_r,         # 그중 연속성 몫 (1~3)
            "capped": pos.capped,             # 현금 부족으로 목표 R 미달성
            "success": success,
        })
        del self.positions[pos.code]

        # 연속성 R 갱신 — 다음에 진입하는 포지션부터 적용된다
        if success:
            self.streak_r = min(C.R_MAX_UNITS, self.streak_r + C.R_STEP)
        else:
            self.streak_r = max(C.R_MIN_UNITS, self.streak_r - C.R_STEP)
        self.streak_log.append((date, pos.code, success, self.streak_r))

    def _sell_all(self, pos, date, price, reason):
        amt = sell_amount(price, pos.qty)
        self.cash += amt
        pos.proceeds_total += amt
        pos.qty = 0
        self._close_position(pos, date, reason)

    def _sell_partial(self, pos, price):
        q = int(pos.qty_init * C.PARTIAL_TP_RATIO)
        # 팔 수량이 0이거나 잔량 전체 이상이면 매도하지 않고 도달 사실만 기록한다.
        #   - RATIO=0 (v24~): 부분익절을 쓰지 않음. +24% 도달 기록은 유지해야
        #     연속성 R 판정(success)이 정상 동작한다
        #   - RATIO=1.0 은 '전량 익절'이 아니라 '익절 안 함'이 된다(잔량 전체이므로)
        if q <= 0 or q >= pos.qty:
            pos.partial_done = True
            return
        amt = sell_amount(price, q)
        self.cash += amt
        pos.proceeds_total += amt
        pos.qty -= q
        pos.partial_done = True

    def _process_exits(self, di, date):
        for code in list(self.positions.keys()):
            pos = self.positions[code]
            p = self.panels[code]
            if not p["valid"][di]:        # 거래정지/미상장 — 보유 유지
                continue

            o, h, l, c = p["open"][di], p["high"][di], p["low"][di], p["close"][di]
            pos.last_close = c

            if pos.pending_ma_exit:
                self._sell_all(pos, date, o,
                               "BEAR_EXIT" if pos.bear_exit else "MA20_EXIT")
                continue

            # v33: 부분익절 이후 잔량은 트레일링으로 끌고 가므로 청산 사유도 달라진다.
            trailing_now = C.TRAILING_STOP or (C.TRAIL_AFTER_TP and pos.partial_done)
            S = pos.stop
            if o <= S:
                self._sell_all(pos, date, o,
                               "TRAIL_GAP" if trailing_now else self._gap_reason)
                continue
            if l <= S:
                self._sell_all(pos, date, S,
                               "TRAIL_INTRA" if trailing_now else self._intra_reason)
                continue

            if (not pos.partial_done) and h >= pos.tp_px:
                self._sell_partial(pos, pos.tp_px)
                # v27: +24% 도달 -> 손절선을 본전으로 올린다.
                # 손절 판정(위)은 이미 끝났으므로 다음 거래일부터 유효하다.
                if C.BREAKEVEN_AFTER_TP:
                    pos.stop = pos.entry_px * (1.0 + C.BREAKEVEN_PCT)

            # 최고가는 항상 갱신한다(v19 고점권 판정에 필요). 손절선을 따라
            # 올리는 것은 TRAILING_STOP 일 때만 — 트레일링은 상승 중 정상적인
            # 조정에도 청산돼 '수익도 짧게' 잘라내므로 v6 부터 끈 상태다.
            if h > pos.highest:
                pos.highest = h
                if C.TRAILING_STOP:
                    pos.stop = h * (1.0 - C.TRAIL_PCT)

            # v33: +24% 부분익절을 마친 뒤에는 잔량을 고점 대비 트레일링으로 끌고 간다.
            #   진입가 -8% 고정손절은 '먹은 걸 다 돌려주는' 구간을 못 막고,
            #   v27 의 본전(0%) 고정은 되돌림 한 번에 잘려 큰 추세를 놓쳤다.
            #   손절선은 내려가지 않는다(max).
            if C.TRAIL_AFTER_TP and pos.partial_done:
                pos.stop = max(pos.stop, pos.highest * (1.0 - C.TRAIL_AFTER_TP_PCT))

            # v19: 고점권에서 거래량이 터진 장대 음봉
            # v22: 종가가 5일선 위면 추세가 살아있다고 보고 팔지 않는다
            if C.BEAR_EXIT and not pos.pending_ma_exit:
                vma = p["value_ma"][di]
                atr = p["atr"][di]
                mb = p["sma_bear"][di]
                trend_broken = (not C.BEAR_MA_PERIOD) or (mb == mb and c < mb)
                if (c < o and atr == atr and vma == vma and trend_broken
                        and (o - c) >= atr * C.BEAR_BODY_ATR
                        and p["value"][di] >= vma * C.BEAR_VOL_MULT
                        and h >= pos.highest * C.BEAR_HIGH_PCT):
                    if C.BEAR_EXIT_AT_CLOSE:      # v25: 당일 종가 즉시 청산
                        self._sell_all(pos, date, c, "BEAR_EXIT")
                        continue
                    pos.pending_ma_exit = True
                    pos.bear_exit = True

            # v14: MA_EXIT_AFTER_TP 면 +24% 에 닿기 전까지는 20일선을 깨도 홀딩한다.
            # 이 경우 유일한 청산 수단은 진입가 -8% 고정손절이다.
            if C.MA_EXIT_AFTER_TP and not pos.partial_done:
                continue
            sma = p["sma20"][di]
            if sma == sma and c < sma:    # NaN 아니고 이탈
                if C.EXIT_AT_CLOSE:       # v22: 신호 당일 종가 청산 (진입과 대칭)
                    self._sell_all(pos, date, c, "MA20_EXIT")
                    continue
                pos.pending_ma_exit = True

    def _equity_now(self):
        v = self.cash
        for pos in self.positions.values():
            v += pos.qty * pos.last_close
        return v

    # ------------------------------------------------------------ 진입
    def _regime_r(self, code, di):
        """종목이 속한 시장(코스피/코스닥) 지수의 당일 국면 R.
        지수 데이터가 없으면 횡보로 둔다. (0.5R 단위이므로 float 로 다룬다)"""
        arr = self.regime_by_index.get(self.market_of.get(code))
        if arr is None:
            return C.REGIME_SIDE
        v = arr[di]
        return C.REGIME_SIDE if v != v else float(v)   # NaN 방어

    def _entry_allowed(self, code, di):
        """v12: 종목이 속한 시장이 기준선 위인가 (코스피 60일선 / 코스닥 120일선).
        보유 포지션의 청산에는 관여하지 않고 신규 진입만 막는다."""
        if not self.market_open:
            return True
        arr = self.market_open.get(self.market_of.get(code))
        return True if arr is None else bool(arr[di])

    def _process_entries(self, di, date, equity):
        slots = C.MAX_POSITIONS - len(self.positions)
        if slots <= 0:
            return
        sigs = self.signal_by_day.get(di)
        if not sigs:
            return
        allowed = self.universe.get("%d-%02d" % (date.year, date.month))
        if not allowed:
            return

        cands = []
        for code in sigs:
            if code in self.positions or code not in allowed:
                continue
            if not self._entry_allowed(code, di):    # v12: 시장별 진입 차단
                self.blocked_signals += 1
                continue
            # v25: 우선순위 기준 — RS 높은 순 / 거래대금 큰 순
            key = (self.panels[code]["rs_raw"][di] if C.ENTRY_PRIORITY == "rs"
                   else self.panels[code]["value"][di])
            if key != key:                        # NaN 방어
                key = -1e18
            cands.append((key, code))
        if not cands:
            return
        cands.sort(reverse=True)          # 거래대금 큰 순

        # v4: Max 2% Rule 기반 1R. 6R 이 곧 '최대 손실 2%'에 해당하는 투입금이다.
        r_unit = equity * C.R_UNIT_PCT
        for _, code in cands[:slots]:
            regime_r = self._regime_r(code, di)
            total_r = regime_r + self.streak_r          # 2R ~ 6R
            target = total_r * r_unit

            px = self.panels[code]["close"][di]
            unit = px * (1.0 + C.SLIPPAGE) * (1.0 + C.FEE_BUY)
            avail = self.cash * 0.9999                 # 반올림으로 현금 초과 방지
            budget = min(target, avail)
            capped = avail < target                    # 목표 R 을 현금이 못 받쳐줌
            qty = int(math.floor(budget / unit))
            if qty <= 0:
                continue
            cost = buy_cost(px, qty)
            if cost > self.cash:
                continue
            self.cash -= cost
            self.positions[code] = Position(code, date, px, qty, cost,
                                            entry_r=total_r, regime_r=regime_r,
                                            streak_r=self.streak_r, capped=capped)

    # ------------------------------------------------------------ 실행
    def run(self, verbose=True):
        n = len(self.days)
        t0 = time.time()
        for di in range(n):
            date = self.days[di]
            self._process_exits(di, date)
            eq = self._equity_now()
            self._process_entries(di, date, eq)
            self.equity.append((date, self._equity_now()))
            if verbose and di % 500 == 0:
                print("  [%.0fs] %s  자산 %.2f억  보유 %d  누적거래 %d"
                      % (time.time() - t0, date.date(), self._equity_now() / 1e8,
                         len(self.positions), len(self.trades)), flush=True)

        last = self.days[-1]
        for code in list(self.positions.keys()):
            self._sell_all(self.positions[code], last,
                           self.positions[code].last_close, "EOD_FORCE")
        if self.equity:
            self.equity[-1] = (last, self._equity_now())

        eq = pd.DataFrame(self.equity, columns=["date", "equity"]).set_index("date")
        tr = pd.DataFrame(self.trades)
        return eq, tr
