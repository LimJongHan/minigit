"""정렬 알고리즘 성능 비교. `python bench_sort.py`

입력 모양 3가지 × 크기별로 실행 시간을 잰다.
- random  : 무작위 정수
- sorted  : 이미 정렬됨 (삽입 정렬의 최선, 순진한 퀵 정렬의 최악)
- few-keys: 값 종류가 5개뿐 (작성자 기준 정렬처럼 동률이 많은 경우)

삽입 정렬은 O(n^2) 이라 큰 입력에서는 건너뛴다(INSERTION_LIMIT).
"""

import random
import time

from minigit.sorting import ALGORITHMS

SIZES = (100, 1_000, 10_000, 50_000)
INSERTION_LIMIT = 10_000
REPEAT = 3


def make_inputs(n, rng):
    return {
        "random": [rng.randint(0, 1_000_000) for _ in range(n)],
        "sorted": list(range(n)),
        "few-keys": [rng.randint(0, 4) for _ in range(n)],
    }


def best_time(func, data):
    """여러 번 재서 가장 빠른 값 — 다른 프로그램 간섭(노이즈)을 줄인다."""
    best = float("inf")
    for _ in range(REPEAT):
        start = time.perf_counter()
        func(data)
        best = min(best, time.perf_counter() - start)
    return best


def main():
    rng = random.Random(0)
    names = list(ALGORITHMS)
    print(f"{'shape':<9} {'n':>7} " + " ".join(f"{name:>11}" for name in names) + "   (ms)")
    for n in SIZES:
        for shape, data in make_inputs(n, rng).items():
            cells = []
            for name in names:
                if name == "insertion" and n > INSERTION_LIMIT:
                    cells.append(f"{'-':>11}")
                    continue
                cells.append(f"{best_time(ALGORITHMS[name], data) * 1000:>11.2f}")
            print(f"{shape:<9} {n:>7} " + " ".join(cells))


if __name__ == "__main__":
    main()
