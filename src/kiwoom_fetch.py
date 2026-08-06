# -*- coding: utf-8 -*-
"""키움 OpenAPI+ 로 종목별 투자자 순매매(opt10059)를 수집한다.

네이버·다음은 '기관 합계'까지만 주지만 키움은 **금융투자·보험·투신·연기금** 등
세부 주체를 모두 준다. 1회 요청에 100일치가 오고 연속조회로 거슬러 올라간다.

    python src/kiwoom_fetch.py

이미 받은 종목은 건너뛰므로 중간에 끊겨도 다시 실행하면 이어서 받는다.

⚠️ 32비트 파이썬에서만 동작한다 (KHOPENAPI OCX 가 32비트).
⚠️ TR 요청은 초당 5회 제한이 있어 REQ_DELAY 간격을 지킨다.
"""
import os
import sys
import time

import pandas as pd
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

TR = "opt10059"
SCREEN = "9001"
REQ_DELAY = 0.3          # TR 요청 간격 (초). 초당 5회 제한 대비 여유
MAX_CALLS = 40           # 종목당 최대 연속조회 횟수 (100일 x 40 = 4,000일)

# opt10059 출력 필드 -> CSV 컬럼
FIELD_MAP = [
    ("일자", "date"), ("현재가", "close"),
    ("개인투자자", "individual"), ("외국인투자자", "foreign"), ("기관계", "inst_total"),
    ("금융투자", "fin_invest"), ("보험", "insurance"), ("투신", "trust"),
    ("기타금융", "other_fin"), ("은행", "bank"), ("연기금등", "pension"),
    ("사모펀드", "private_fund"), ("국가", "nation"), ("기타법인", "other_corp"),
    ("내외국인", "foreign_domestic"),
]


def log(msg):
    print(msg, flush=True)


class Kiwoom(object):
    def __init__(self):
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.ocx.OnEventConnect.connect(self._on_connect)
        self.ocx.OnReceiveTrData.connect(self._on_tr)
        self.loop = None
        self.rows = []
        self.has_next = False

    def _quit(self):
        if self.loop is not None and self.loop.isRunning():
            self.loop.quit()

    def _on_connect(self, err):
        log("[로그인] 결과코드 %d (%s)" % (err, "성공" if err == 0 else "실패"))
        self._quit()

    def _on_tr(self, screen, rqname, trcode, recordname, prev_next, *args):
        n = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        for i in range(n):
            rec = {}
            for src, dst in FIELD_MAP:
                v = self.ocx.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, i, src)
                rec[dst] = v.strip()
            if rec["date"]:
                self.rows.append(rec)
        self.has_next = (prev_next == "2")
        self._quit()

    def wait(self, ms=30000):
        self.loop = QEventLoop()
        QTimer.singleShot(ms, self._quit)
        self.loop.exec_()

    def connect(self):
        if self.ocx.dynamicCall("GetConnectState()") == 1:
            log("[로그인] 이미 연결됨")
            return True
        log("[로그인] CommConnect 호출 — 로그인 창이 뜨면 완료해 주세요")
        self.ocx.dynamicCall("CommConnect()")
        self.wait(180000)
        return self.ocx.dynamicCall("GetConnectState()") == 1

    def fetch_stock(self, code, start_date):
        """한 종목을 start_date 까지 거슬러 수집. 실패 시 None."""
        self.rows = []
        prev_next = 0
        for call in range(MAX_CALLS):
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "일자", "")
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "금액수량구분", "2")
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "매매구분", "0")
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "단위구분", "1")
            before = len(self.rows)
            rc = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                      "investor", TR, prev_next, SCREEN)
            if rc != 0:                       # -200 시세과부하 / -201 조회제한 등
                log("    [경고] %s CommRqData rc=%d — 5초 대기 후 재시도" % (code, rc))
                time.sleep(5.0)
                continue
            self.wait()
            time.sleep(REQ_DELAY)
            if len(self.rows) == before:      # 더 안 옴
                break
            if self.rows[-1]["date"] <= start_date:
                break
            if not self.has_next:
                break
            prev_next = 2
        return self.rows or None


def main():
    start_date = C.DATA_START                  # "20150101"
    os.makedirs(C.INVESTOR_DIR, exist_ok=True)
    codes = open(os.path.join(C.DATA, "universe_codes.txt")).read().split()
    todo = [c for c in codes if not os.path.exists(
        os.path.join(C.INVESTOR_DIR, "%s.csv" % c))]
    log("[투자자] 대상 %d개 (캐시 %d개 건너뜀)" % (len(todo), len(codes) - len(todo)))
    if not todo:
        return

    app = QApplication(sys.argv)
    k = Kiwoom()
    if not k.connect():
        raise SystemExit("[중단] 키움 로그인 실패")

    t0, fails = time.time(), []
    for i, code in enumerate(todo, 1):
        rows = k.fetch_stock(code, start_date)
        if not rows:
            fails.append(code)
        else:
            df = pd.DataFrame(rows).drop_duplicates(subset=["date"])
            for c in df.columns:
                if c != "date":
                    df[c] = pd.to_numeric(df[c].str.replace("+", "", regex=False),
                                          errors="coerce")
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
            df = df[df["date"] >= pd.Timestamp(start_date)].sort_values("date")
            df["close"] = df["close"].abs()     # 부호는 등락 표시라 절대값 사용
            df.to_csv(os.path.join(C.INVESTOR_DIR, "%s.csv" % code), index=False)
        if i % 10 == 0:
            el = time.time() - t0
            log("  %4d/%d  %.1f분 경과  실패 %d  (잔여 약 %.0f분)"
                % (i, len(todo), el / 60, len(fails), el / i * (len(todo) - i) / 60))
    log("[투자자] 완료 %d개, 실패 %d개  총 %.1f분"
        % (len(todo) - len(fails), len(fails), (time.time() - t0) / 60))
    if fails:
        log("  실패 목록(앞 20개): %s" % fails[:20])


if __name__ == "__main__":
    main()
