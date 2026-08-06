# -*- coding: utf-8 -*-
"""키움 OpenAPI+ 연결 및 opt10059(종목별투자자기관별) 형식 검증용 프로브.

본격 수집 전에 아래를 확인한다.
  1) 로그인이 되는가 (자동로그인 설정 시 창 없이 진행)
  2) opt10059 가 금융투자 등 세부 주체를 주는가
  3) 1회 요청당 며칠치가 오는가, 연속조회로 얼마나 거슬러 갈 수 있는가

    python src/kiwoom_probe.py [종목코드]

⚠️ 32비트 파이썬에서만 동작한다 (KHOPENAPI OCX 가 32비트).
"""
import sys

from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop, QTimer
from PyQt5.QtWidgets import QApplication

TR = "opt10059"
SCREEN = "9001"
# opt10059 출력 필드 (키움 개발가이드)
FIELDS = ["일자", "현재가", "전일대비", "누적거래대금", "개인투자자", "외국인투자자",
          "기관계", "금융투자", "보험", "투신", "기타금융", "은행", "연기금등",
          "사모펀드", "국가", "기타법인", "내외국인"]


class Probe(object):
    def __init__(self):
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self.ocx.OnEventConnect.connect(self._on_connect)
        self.ocx.OnReceiveTrData.connect(self._on_tr)
        self.loop = None
        self.rows = []
        self.has_next = False

    # ---------------- 이벤트 ----------------
    def _quit(self):
        if self.loop is not None and self.loop.isRunning():
            self.loop.quit()

    def _on_connect(self, err):
        print("[로그인] 결과코드 %d (%s)" % (err, "성공" if err == 0 else "실패"))
        self._quit()

    def _on_tr(self, screen, rqname, trcode, recordname, prev_next, *args):
        cnt = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        for i in range(cnt):
            rec = {}
            for f in FIELDS:
                v = self.ocx.dynamicCall(
                    "GetCommData(QString, QString, int, QString)",
                    trcode, rqname, i, f)
                rec[f] = v.strip()
            self.rows.append(rec)
        self.has_next = (prev_next == "2")
        self._quit()

    # ---------------- 동작 ----------------
    def wait(self, ms=60000):
        self.loop = QEventLoop()
        QTimer.singleShot(ms, self._quit)          # 타임아웃 방어
        self.loop.exec_()

    def connect(self):
        state = self.ocx.dynamicCall("GetConnectState()")
        if state == 1:
            print("[로그인] 이미 연결됨")
            return True
        print("[로그인] CommConnect 호출 — 로그인 창이 뜨면 완료해 주세요")
        self.ocx.dynamicCall("CommConnect()")
        self.wait(180000)                          # 로그인은 넉넉히 3분
        return self.ocx.dynamicCall("GetConnectState()") == 1

    def request(self, code, date, prev_next=0):
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "일자", date)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "금액수량구분", "2")  # 2=수량
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "매매구분", "0")      # 0=순매수
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "단위구분", "1")      # 1=단주
        self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                             "investor", TR, prev_next, SCREEN)
        self.wait()


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else "005930"
    app = QApplication(sys.argv)
    p = Probe()
    if not p.connect():
        print("[중단] 로그인 실패")
        return

    print("[요청] %s opt10059 (1회차)" % code)
    p.request(code, "20260807")
    print("[결과] %d행 수신, 연속조회 가능=%s" % (len(p.rows), p.has_next))
    if not p.rows:
        print("[중단] 데이터 없음")
        return

    print("\n=== 수신 필드 (첫 행) ===")
    for k, v in p.rows[0].items():
        print("  %-12s %s" % (k, v))

    print("\n=== 최근 5행 (일자 / 기관계 / 금융투자 / 외국인) ===")
    for r in p.rows[:5]:
        print("  %s  기관계 %12s  금융투자 %12s  외국인 %12s"
              % (r["일자"], r["기관계"], r["금융투자"], r["외국인투자자"]))

    print("\n[요약] 1회 요청당 %d일치, 기간 %s ~ %s"
          % (len(p.rows), p.rows[-1]["일자"], p.rows[0]["일자"]))
    print("       555종목 x 10년(약 2,600일) 기준 종목당 약 %d회 요청 필요"
          % (2600 // max(1, len(p.rows)) + 1))


if __name__ == "__main__":
    main()
