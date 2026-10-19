"""시연 스크립트(structure · concepts · whatif)가 같이 쓰는 준비물 — 고정 시계와 features.txt 와 같은 이력.

최종 그래프 (화살표 = 자식 → 부모), --fixed-clock 과 같은 시계라 hash 도 features.txt 와 같다:

    A ← P ← M1 ← M2        A  4280179 Set up project        P  7333cf5 Add cart feature
    A ← L ← F  ← M2        L  1cdd61f Add signup feature     F  8ff2dea Fix SIGNUP, signout bug
        L ← M1             M1 70cfbfe merge(P, L)           M2 a16e116 merge(M1, F)
"""

import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from minigit import MiniGitCLI, Repository  # noqa: E402

DIAMOND_SCRIPT = [
    "init Ari", "commit 'Set up project'", "branch feature", "switch feature",
    "commit 'Add signup feature'", "switch main", "commit 'Add cart feature'",
    "merge feature", "init Ben", "switch feature", "commit 'Fix SIGNUP, signout bug'",
    "switch main", "merge feature",
]
NAMES = {"4280179": "A", "1cdd61f": "L", "7333cf5": "P", "70cfbfe": "M1", "8ff2dea": "F", "a16e116": "M2"}


class StepClock:
    """main.py --fixed-clock 과 같은 시계: 2025-03-10 09:00:00 부터 부를 때마다 15분."""

    def __init__(self, start=datetime(2025, 3, 10, 9, 0, 0), step=timedelta(minutes=15)):
        self.now, self.step = start, step

    def __call__(self):
        current = self.now
        self.now += self.step
        return current


def build_diamond():
    """기능 시연(features.txt)과 같은 이력을 만들어 (repo, cli) 를 돌려준다."""
    repo = Repository(clock=StepClock())
    cli = MiniGitCLI(repo)
    for line in DIAMOND_SCRIPT:
        cli.execute(line)
    return repo, cli


def label(h):
    """hash 옆에 A/L/P/M1/F/M2 별명을 붙여 읽기 쉽게."""
    return f"{h}({NAMES[h]})" if h in NAMES else h


def section(title):
    print(f"\n{'═' * 72}\n {title}\n{'═' * 72}")
