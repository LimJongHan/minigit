"""라이브 데모용 저장소를 미리 깔아 둔다 — 시연 이력(A · L · P · M1 · F · M2)까지.

사용법:
  python3 demo-setting.py           # 이력을 만들고 커밋 표 · 브랜치 · 그림을 출력한다
  python3 demo-setting.py --shell   # 만든 뒤 그 상태 그대로 mini-git> 프롬프트로 들어간다

시계는 main.py --fixed-clock 과 같다(09:00 부터 커밋마다 15분). 그래서 hash 가
demo/features.txt · docs/*.png 와 똑같다. --shell 에서 아래처럼 치면 이어지는 커밋도 같은 hash 가 나온다.

  commit --date="2025-03-10 08:00:00" "Commit from a skewed clock"   → 828a093 (S)
  switch --orphan docs  →  commit "Docs root"                        → 013f26e (D)

데모 중에 상태를 바꿨다면 다시 실행하면 처음 상태로 돌아간다(전부 메모리 안이라 지울 파일이 없다).
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "demo"))

from scenario import NAMES, build_diamond  # noqa: E402

from minigit import PROMPT  # noqa: E402

PICTURE = """\
  간선 (자식 → 부모):  P → A   L → A   M1 → P, L   F → L   M2 → M1, F
  흐름:  A ← P ← M1 ← M2   ·   A ← L ← F ← M2   ·   L ← M1      그림: docs/commit-graph.png"""


def summary(repo):
    print("\n  별명  hash      작성자  시각   부모                      메시지")
    print("  ────  ───────   ──────  ─────  ────────────────────────  ─────────────────────────────")
    for c in repo.store.all():
        parents = ", ".join(f"{p}({NAMES[p]})" for p in c.parents) or "-"
        print(f"  {NAMES[c.hash]:<4}  {c.hash}   {c.author:<6}  {c.timestamp:%H:%M}  {parents:<24}  {c.message}")
    print("\n  브랜치: " + "   ".join(
        f"{'*' if name == repo.head else ' '}{name} → {target}({NAMES[target]})" for name, target in repo.branches.items()))
    print(f"  현재 사용자: {repo.user}\n")
    print(PICTURE)


def shell(cli):
    """main.repl 과 같은 루프를, 미리 만든 저장소로 돈다."""
    print("\n  이어서 직접 입력한다. 끝내려면 exit\n")
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        output, keep_running = cli.execute(line)
        if output:
            print(output)
        if not keep_running:
            break


if __name__ == "__main__":
    repo, cli = build_diamond()
    print("  ✓ demo/scenario.py 의 이력을 재생했다 (--fixed-clock 과 같은 시계)")
    summary(repo)
    if "--shell" in sys.argv[1:]:
        shell(cli)
