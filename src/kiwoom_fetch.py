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
REQ_DELAY = 0.25         # TR 요청 간격 (초). 초당 5회 제한 대비 여유
MAX_CALLS = 40           # 종목당 최대 연속조회 횟수 (100일 x 40 = 4,000일)
# 완전 수집 판정: 고정 행수로 보면 늦게 상장한 종목(예: 009900 은 2020-12 상장,
# 1,389행이 전부)을 영원히 실패 처리해 매 사이클 슬롯을 낭비한다. 따라서
# "테스트 시작일까지 닿았는가" 또는 "더 받을 게 없는가(exhausted)"로 판정한다.
COVER_DATE = "20160104"  # 이 날짜까지 닿으면 완전 수집으로 본다
BATCH = 3                # 한 프로세스가 처리할 종목 수 (이후 종료)

# ⚠️ 키움 조회제한 (공식 안내 + 실측)
#   - 1초당 5회 외에 분당/시간당 '유동적' 제한이 있고 기준은 비공개
#   - 제한이 걸리면 대기로는 풀리지 않고 **프로그램을 다시 실행**해야 복구된다
#     (CommTerminate + CommConnect 재호출로는 안 풀림 — 실측 확인)
#   - 실측: 새 프로세스마다 정확히 3종목(약 90회 요청)까지 완전 수집됨
#   따라서 BATCH 만큼만 처리하고 종료하며, 셸에서 반복 실행한다:
#     while :; do python src/kiwoom_fetch.py || break; done

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
        self.expect_rq = ""       # 현재 기다리는 요청명 (응답 대조용)
        self.received = 0         # 직전 응답에서 받은 행 수

    def _quit(self):
        if self.loop is not None and self.loop.isRunning():
            self.loop.quit()

    def _on_connect(self, err):
        log("[로그인] 결과코드 %d (%s)" % (err, "성공" if err == 0 else "실패"))
        self._quit()

    def _on_tr(self, screen, rqname, trcode, recordname, prev_next, *args):
        # ⚠️ 요청명이 다르면 이전 요청의 늦은 응답이다. 받아들이면 다른 종목
        #    데이터가 섞여 저장되므로 반드시 버린다.
        if rqname != self.expect_rq:
            log("    [무시] 예상 %s / 수신 %s" % (self.expect_rq, rqname))
            return
        n = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        got = 0
        for i in range(n):
            rec = {}
            for src, dst in FIELD_MAP:
                v = self.ocx.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, i, src)
                rec[dst] = v.strip()
            if rec["date"]:
                self.rows.append(rec)
                got += 1
        self.received = got
        self.has_next = (prev_next == "2")
        self._quit()

    def wait(self, ms=30000):
        self.loop = QEventLoop()
        QTimer.singleShot(ms, self._quit)
        self.loop.exec_()

    def connect(self):
        if self.ocx.dynamicCall("GetConnectState()") == 1:
            return True
        self.ocx.dynamicCall("CommConnect()")
        self.wait(180000)
        return self.ocx.dynamicCall("GetConnectState()") == 1

    def fetch_stock(self, code, start_date, base_date):
        """한 종목을 start_date 까지 거슬러 수집. 실패 시 None.

        주의: opt10059 는 '일자'(기준일자)가 필수다. 비워 두면 조회는 성공(rc=0)
        하지만 빈 결과가 돌아온다.
        """
        self.rows = []
        prev_next, retries = 0, 0
        for call in range(MAX_CALLS):
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "일자", base_date)
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "금액수량구분", "2")
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "매매구분", "0")
            self.ocx.dynamicCall("SetInputValue(QString, QString)", "단위구분", "1")

            # 요청명은 **종목당 하나로 고정**한다. 연속조회(prev_next=2)는 최초
            # 요청과 같은 이름이어야 하며(다르면 rc=-300), 종목마다 다르므로
            # 다른 종목의 늦은 응답은 _on_tr 에서 걸러진다.
            self.expect_rq = "inv_%s" % code
            self.received = 0
            rc = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                      self.expect_rq, TR, prev_next, SCREEN)
            if rc != 0:                       # -200 시세과부하 / -201 조회제한 등
                log("    [경고] %s CommRqData rc=%d — 5초 대기 후 재시도" % (code, rc))
                time.sleep(5.0)
                retries += 1
                if retries > 5:
                    break
                continue
            self.wait()
            time.sleep(REQ_DELAY)

            if self.received == 0:            # 응답 없음/불일치 — 한 번 더 시도
                retries += 1
                if retries > 3:
                    break
                time.sleep(1.0)
                continue
            if self.rows[-1]["date"] <= start_date:
                break
            if not self.has_next:
                break
            prev_next = 2
        self.expect_rq = ""                   # 뒤늦은 응답이 다음 종목에 섞이지 않도록
        # exhausted = 서버에 더 줄 데이터가 없어서 멈춤 (상장 이전까지 다 받음)
        return (self.rows or None), (not self.has_next)


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

    base_date = time.strftime("%Y%m%d")        # 기준일자 = 오늘 (필수 입력값)
    t0, fails = time.time(), []
    batch = todo[:BATCH]                       # 조회제한 때문에 BATCH 개만 처리하고 종료
    for i, code in enumerate(batch, 1):
        globals()["SCREEN"] = str(9100 + i)
        k.ocx.dynamicCall("DisconnectRealData(QString)", SCREEN)
        rows, exhausted = k.fetch_stock(code, start_date, base_date)
        complete = bool(rows) and (rows[-1]["date"] <= COVER_DATE or exhausted)
        if not complete:
            fails.append((code, len(rows) if rows else 0))
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
    done = len(batch) - len(fails)
    log("[투자자] 이번 배치 %d/%d 성공, 남은 종목 %d개 (%.0f초)"
        % (done, len(batch), len(todo) - done, time.time() - t0))
    if fails:
        log("  미완: %s" % fails)
    # 셸 반복문이 종료 조건을 알 수 있도록: 남은 게 없으면 0, 있으면 10
    sys.exit(0 if len(todo) - done <= 0 else 10)


if __name__ == "__main__":
    main()
