# -*- coding: utf-8 -*-
"""2단계: 다음 데이터로 시점별 유니버스를 만들고, 그 종목만 네이버 수정주가를 받는다."""
import os
import pickle
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import fetch
import universe as U


def main():
    tickers = pd.read_csv(os.path.join(C.DATA, "tickers.csv"), dtype={"code": str})
    codes = tickers["code"].tolist()
    have = [c for c in codes if os.path.exists(os.path.join(C.DAUM_DIR, "%s.csv" % c))]
    print("[준비] 다음 데이터 보유 종목: %d/%d" % (len(have), len(codes)), flush=True)

    uni_path = os.path.join(C.DATA, "universe.pkl")
    sig = U.filter_signature()
    cached = None
    if os.path.exists(uni_path):
        with open(uni_path, "rb") as f:
            cached = pickle.load(f)
    if cached is not None and cached.get("sig") == sig:
        uni = cached["uni"]
        print("[유니버스] 캐시 사용 (필터 조건 동일)", flush=True)
    else:
        if cached is not None:
            print("[유니버스] 필터 조건 변경 감지 -> 재계산", flush=True)
        print("[유니버스] 월말 스캔 시작...", flush=True)
        uni = U.build_universe(have)
        with open(uni_path, "wb") as f:
            pickle.dump({"sig": sig, "uni": uni}, f)

    # 백테스트 기간에 한 번이라도 유니버스에 든 종목만 추림
    lo, hi = C.TEST_START[:7], C.TEST_END[:7]
    need = set()
    for ym, s in uni.items():
        if lo <= ym <= hi:
            need |= s
    need = sorted(need)

    s = U.summarize({k: v for k, v in uni.items() if lo <= k <= hi})
    print("\n[유니버스] 월별 종목 수")
    print("  기간: %s ~ %s (%d개월)" % (s.index[0], s.index[-1], len(s)))
    print("  평균 %.0f개 / 최소 %d개 / 최대 %d개" % (s.mean(), s.min(), s.max()))
    print("  샘플:", ", ".join("%s:%d" % (k, s[k]) for k in list(s.index)[::18]))
    print("\n[유니버스] 기간 중 한 번이라도 편입된 종목: %d개" % len(need), flush=True)

    with open(os.path.join(C.DATA, "universe_codes.txt"), "w") as f:
        f.write("\n".join(need))

    print("\n[네이버] 수정주가 수집 시작 (%d개)" % len(need), flush=True)
    fetch.run_naver(need)


if __name__ == "__main__":
    main()
