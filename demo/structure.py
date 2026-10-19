"""구조 시연 — 구조 · 책임 분리 · 해시맵 · 역색인 갱신 시점 · 탐색 재사용 · docstring 기준.

    python3 demo/structure.py

설명형 문항이라 '말' 대신 **내부 상태를 직접 찍어서** 보여준다. 시계를 고정해 hash 가 매번 같다.
"""

import ast
import os
import tracemalloc
from datetime import datetime

from scenario import ROOT, StepClock, build_diamond, section

from minigit import MiniGitCLI, Repository
from minigit import commit as commit_module
from minigit import graph
from minigit.commit import CommitStore


def show_state(repo, label):
    print(f"\n[{label}]")
    print(f"  user     = {repo.user!r}")
    print(f"  head     = {repo.head!r}            ← 브랜치 '이름' 을 가리킨다")
    print(f"  branches = {repo.branches}   ← 이름 → hash")
    print(f"  store    = {len(repo.store)} commits    ← hash → Commit")


# ─────────────────────────────────────────────────────────────────────
section("2-1. 저장소 · 브랜치 · HEAD · 사용자 — 무엇을 어디에 두었나")
repo = Repository(clock=StepClock())
cli = MiniGitCLI(repo)
print("""
  Repository (minigit/repository.py)  — 명령의 '의미' 만 안다. 상태는 아래 4개가 전부
  ├── user      : str                  현재 작성자 (INIT 이 설정)
  ├── head      : str                  현재 브랜치 '이름'
  ├── branches  : dict[name → hash]    이름표. 커밋을 복사하지 않는다
  ├── store     : CommitStore          hash → Commit 해시맵 (minigit/commit.py)
  └── index     : CommitIndex          keyword / author 역색인 (minigit/index.py)

  알고리즘(graph.py · sorting.py · index.py)은 Repository 를 모른다 → 혼자 테스트 가능
  출력 문자열은 cli.py 만 만든다 → 엔진은 '값' 만 돌려준다""")
cli.execute("init Ari")
show_state(repo, "INIT Ari 직후")
cli.execute("commit 'Set up project'")
cli.execute("branch feature")
show_state(repo, "COMMIT + BRANCH feature 직후 — 두 이름표가 같은 hash")
cli.execute("switch feature")
cli.execute("commit 'Add signup feature'")
show_state(repo, "SWITCH feature + COMMIT 직후 — feature 만 전진")

# ─────────────────────────────────────────────────────────────────────
section("2-2. hash 로 빠르게 찾기 — 해시맵 + 중복/충돌 방지")
store = repo.store
print("\n  CommitStore._commits 의 실제 내용 (dict: hash → Commit):")
for h, c in store._commits.items():
    print(f"    {h!r}: Commit(message={c.message!r}, parents={c.parents}, seq={c.seq})")
target = repo.branches["feature"]
print(f"\n  store.get({target!r}) → {store.get(target).message!r}   (dict 조회, 평균 O(1) — 몇 개든 한 번)")
print(f"  {target!r} in store → {target in store}")

print("\n  hash = SHA-1( seq · author · message · timestamp · parents · nonce ) 앞 7자")
print("  → seq(생성 순번)가 재료라서 같은 메시지·같은 시각이라도 입력이 다르다")
print("  → 그래도 7자로 자르면 충돌이 '불가능' 은 아니다 → 이미 있으면 nonce+1 로 다시 만든다")

print("\n  강제 충돌 실험: HASH_LENGTH 를 1 로 줄이면 16가지뿐 → 충돌이 반드시 난다")
original = commit_module.HASH_LENGTH
commit_module.HASH_LENGTH = 1
try:
    tiny = CommitStore()
    ts = datetime(2024, 1, 1)
    made = [tiny.create("same", "same", ts).hash for _ in range(16)]
    print(f"    16개 생성: {made}")
    print(f"    서로 다른 개수: {len(set(made))} / 16   ← 충돌 났지만 재생성으로 전부 다름")
    try:
        tiny.create("same", "same", ts)
    except RuntimeError as exc:
        print(f"    17번째: {type(exc).__name__}: {exc}   ← 공간이 꽉 차면 무한 루프 대신 즉시 실패")
    full = MiniGitCLI(Repository(clock=StepClock()))
    for line in ["init A"] + [f"commit c{i}" for i in range(16)]:
        full.execute(line)
    print(f"    CLI 에서 17번째 커밋 → {full.execute('commit c17')[0]!r}   ← 그 커밋만 거부, REPL 은 계속")
finally:
    commit_module.HASH_LENGTH = original

tracemalloc.start()
probe = Repository(clock=StepClock())
probe.init("dev")
for i in range(20_000):
    probe.commit(f"commit number {i} fix signup bug")
per_commit = tracemalloc.get_traced_memory()[0] / 20_000
tracemalloc.stop()
print(f"\n  16^7 칸을 다 채울 수 있나? 커밋 1개(저장소 + 역색인) ≈ {per_commit:.0f} bytes"
      f" → 16^7 개면 약 {per_commit * 16 ** 7 / 1e9:,.0f} GB")
print("  → 가드는 이론상 한계. 현실에선 메모리가 먼저 막히고, 빈 칸이 줄수록 nonce 재시도가 늘어 느려진다")

# ─────────────────────────────────────────────────────────────────────
section("2-3. 역색인은 언제 · 어떻게 갱신되나")
idx = repo.index
print("\n  갱신 시점: Repository.commit() 안에서, 커밋이 저장소에 들어간 '직후' 한 번")
print("           (store.create → branches 전진 → index.add_commit)")
print("  갱신 방식: 메시지를 tokenize(lower + split + 양끝 문장부호 제거) → 토큰마다 posting 끝에 hash 추가")
print(f"\n  [커밋 전] keyword 키 {len(idx.keywords)}개, 'fix' → {idx.keywords.get('fix')}, 'signup' → {idx.keywords.get('signup')}")
cli.execute("init Ben")
out, _ = cli.execute('commit "Fix SIGNUP, signout bug"')
print(f"  > {out}")
print(f"  [커밋 후] keyword 키 {len(idx.keywords)}개, 'fix' → {idx.keywords.get('fix')}, 'signup' → {idx.keywords.get('signup')}")
print(f"           author 'ben' → {idx.authors.get('ben')}, 'ari' → {idx.authors.get('ari')}")
print("\n  posting 이 생성순으로 쌓이는 이유: 커밋이 한 번에 하나씩, 순서대로 들어오기 때문")
print("  → 같은 메시지에 같은 단어가 두 번 나와도 posting 의 '마지막 원소' 만 보면 중복을 막는다 (O(1))")
cli.execute("commit 'signup signup signup'")
print(f"  'signup signup signup' 커밋 후 'signup' → {idx.keywords.get('signup')}  (새 hash 는 한 번만)")

# ─────────────────────────────────────────────────────────────────────
section("2-4. LOG · PATH · ANCESTORS 가 같은 그래프 함수를 재사용하는 구조")
# 기능 시연(features.txt)과 같은 다이아몬드 이력 (A · L · P · M1 · F · M2) — demo/scenario.py
g, _ = build_diamond()
pm = g.parents_map()
names = {h: c.message[:22] for h, c in g.store._commits.items()}
print("\n  세 명령의 입력은 단 하나: parents_map = {hash: (부모 hash, ...)}  — Repository.parents_map()")
for h, parents in pm.items():
    print(f"    {h!r}: {str(parents):<26}  # {names[h]}")
print("""
  graph.py 의 공용 부품 → 명령
    build_children()        부모→자식 뒤집기       → topological_order  (LOG)
    undirected_adjacency()  양방향 이웃            → shortest_path      (PATH)
    bfs_distances()         BFS 거리표             → shortest_path      (PATH)
    ancestors()             부모 방향 BFS + seen   → ANCESTORS, is_ancestor (MERGE 'Already up to date')
  세 함수 모두 Repository 를 import 하지 않는다 — 딕셔너리만 받는다""")
head = g.branches["main"]
seq_of = {h: c.seq for h, c in g.store._commits.items()}
print(f"  LOG       topological_order(pm, priority=seq)      → {graph.topological_order(pm, priority=seq_of.__getitem__)}")
print("            (Repository.log 는 동률을 생성 순번 seq 로 깬다. priority 를 안 주면 hash 문자열 순)")
print(f"  PATH      shortest_path(pm, '7333cf5', '1cdd61f')  → {graph.shortest_path(pm, '7333cf5', '1cdd61f')}")
print(f"  ANCESTORS ancestors(pm, {head!r})                → {graph.ancestors(pm, head)}")
print(f"  MERGE     is_ancestor(pm, '1cdd61f', {head!r})   → {graph.is_ancestor(pm, '1cdd61f', head)}")
print("\n  저장소 없이 손으로 만든 딕셔너리에도 그대로 쓴다 (테스트의 브루트포스 대조가 이렇게 돈다):")
diamond = {"a": (), "b": ("a",), "c": ("a",), "d": ("c", "b")}
print(f"    diamond = {diamond}")
print(f"    topological_order → {graph.topological_order(diamond)}")
print(f"    shortest_path d→a → {graph.shortest_path(diamond, 'd', 'a')}")
print(f"    ancestors(d)      → {graph.ancestors(diamond, 'd')}")

# ─────────────────────────────────────────────────────────────────────
section("2-5. docstring · 주석 작성 기준 — 실제 커버리지")
print("""
  기준
  ① 모든 모듈 첫머리: 이 파일이 '무엇을 책임지는가' + 핵심 아이디어 한 줄
  ② 알고리즘 함수: 무엇을 · 어떻게(단계) · 왜 맞는가 · 복잡도 (예: shortest_path 의 '왜 욕심이 맞나')
  ③ 주석은 '무엇' 이 아니라 '왜' — 코드만 봐선 모르는 이유 (예: list.pop(0) 대신 head 를 쓰는 이유)
  ④ 정답이 하나가 아닌 결정은 docstring 에 근거와 함께 (예: 재-INIT 은 이력 유지 — git init 과 같음)""")
print(f"\n  {'파일':<26}{'모듈':>6}{'클래스':>10}{'함수':>12}")
for name in ("commit", "graph", "sorting", "index", "repository", "cli", "diff"):
    path = os.path.join(ROOT, "minigit", f"{name}.py")
    tree = ast.parse(open(path, encoding="utf-8").read())
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("__")]
    c_doc = sum(1 for n in classes if ast.get_docstring(n))
    f_doc = sum(1 for n in funcs if ast.get_docstring(n))
    mod = "✔" if ast.get_docstring(tree) else "✘"
    print(f"  minigit/{name + '.py':<18}{mod:>6}{f'{c_doc}/{len(classes)}':>10}{f'{f_doc}/{len(funcs)}':>12}")
print("\n  docstring 이 없는 함수 — 감싼 쪽(모듈·클래스·공개 함수)이 대신 설명하는 것들:")
for name in ("commit", "sorting", "index", "repository", "cli", "diff"):
    tree = ast.parse(open(os.path.join(ROOT, "minigit", f"{name}.py"), encoding="utf-8").read())
    missing = [n.name for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and not n.name.startswith("__") and not ast.get_docstring(n)]
    print(f"    {name + '.py':<15} {', '.join(missing)}")
print("""
  → cmd_* 명령 핸들러는 HELP_TEXT 와 README 명령표가, push/pop/_sift_down 은 MinHeap 클래스 docstring 이,
    _merge_sort_pairs 는 merge_sort 의, _make_hash 는 CommitStore 의, lcs_table 은 diff.py 모듈 docstring 이 설명한다.
    graph.py(알고리즘 7개)는 예외 없이 전부 있다 — '알고리즘은 함수 단위로, 배선은 묶음 단위로' 가 기준""")
print("\n  예: graph.shortest_path 의 docstring 첫 줄 →", ast.get_docstring(
    [n for n in ast.walk(ast.parse(open(os.path.join(ROOT, "minigit", "graph.py"), encoding="utf-8").read()))
     if isinstance(n, ast.FunctionDef) and n.name == "shortest_path"][0]).splitlines()[0])
