# -*- coding: utf-8 -*-
"""버전 아카이브 — 실행에 사용한 스펙과 그 결과 리포트를 한 쌍으로 보관한다.

백테스트를 돌린 직후, 스펙을 다시 수정하기 전에 실행할 것.

    python src/archive_version.py v3 "RS 절대기준으로 변경"

스펙만 있으면 결과를 알 수 없고 리포트만 있으면 어떤 조건에서 나온 숫자인지 알 수
없으므로 반드시 함께 남긴다. (v1 스펙을 이 규칙이 없어 유실한 전례가 있다.)
"""
import datetime
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

SPEC = os.path.join(C.ROOT, "backtest_spec.md")
REPORT = os.path.join(C.OUT, "report.md")


def archive(version, note=""):
    dst = os.path.join(C.OUT, "history", version)
    if os.path.exists(dst):
        raise SystemExit("이미 존재합니다: %s\n덮어쓰려면 먼저 삭제하세요." % dst)
    for src in (SPEC, REPORT):
        if not os.path.exists(src):
            raise SystemExit("파일이 없습니다: %s" % src)

    # 리포트가 스펙보다 오래됐다면 스펙 수정 후 백테스트를 안 돌린 것이다.
    if os.path.getmtime(REPORT) < os.path.getmtime(SPEC):
        print("[경고] report.md 가 backtest_spec.md 보다 오래됐습니다.")
        print("       스펙을 바꾼 뒤 백테스트를 다시 돌리지 않았을 수 있습니다.")
        if input("       그래도 진행할까요? [y/N] ").strip().lower() != "y":
            raise SystemExit("중단했습니다.")

    os.makedirs(dst)
    today = datetime.date.today().isoformat()

    for src, name, what in ((SPEC, "spec.md", "스펙 문서"),
                            (REPORT, "report.md", "결과 리포트")):
        with open(src, encoding="utf-8") as f:
            body = f.read()
        # note 에 '%' 가 들어갈 수 있으므로(예: "Max 2% Rule") % 포맷을 쓰지 않는다
        header = ["<!--", "  아카이브: " + version + " 백테스트 실행 시점의 "
                  + what + " (" + today + ")"]
        if note:
            header.append("  메모: " + note)
        header += ["-->", "", ""]
        with open(os.path.join(dst, name), "w", encoding="utf-8") as f:
            f.write("\n".join(header) + body)

    print("[아카이브] %s -> %s" % (version, dst))
    print("  spec.md   (%s 기준 스펙)" % version)
    print("  report.md (%s 실행 결과)" % version)
    print("\n다음: output/history/README.md 표와 output/CHANGELOG.md 에 항목을 추가하세요.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    archive(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
