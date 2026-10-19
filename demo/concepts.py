"""개념 시연 — DAG · 위상 정렬 · BFS 와 무방향 간선 · 정렬 복잡도/안정성 · 역색인.

    python3 demo/concepts.py

개념 문항이라 '그렇다' 고 말하는 대신, **반례를 만들어 깨지는 장면**을 보여준다.
"""

import dataclasses
import random
import time
from datetime import datetime

from scenario import build_diamond, label, section

from minigit import graph
from minigit.commit import CommitStore
from minigit.index import CommitIndex, tokenize
from minigit.sorting import ALGORITHMS, MinHeap

# ─────────────────────────────────────────────────────────────────────
section("3-1. 커밋 그래프는 왜 DAG 여야 하나 — 사이클을 일부러 만들어 보면")
store = CommitStore()
root = store.create("root", "A", datetime(2024, 1, 1))
print("\n  ① 사이클을 만들 길이 코드에서 막혀 있다")
try:
    root.parents = ("someone",)
except dataclasses.FrozenInstanceError as exc:
    print(f"    이미 만든 커밋의 부모 바꾸기      → FrozenInstanceError: {exc}")
try:
    store.create("child", "A", datetime(2024, 1, 1), parents=("not-yet",))
except ValueError as exc:
    print(f"    아직 없는(미래의) 커밋을 부모로  → ValueError: {exc}")
print("    → 간선은 항상 '새 커밋 → 이미 있던 커밋' 으로만 생긴다 → 되돌아오는 길이 생길 수 없다")

print("\n  ② 그래도 사이클이 있다면? — 손으로 만든 x → y → z → x")
cycle = {"x": ("z",), "y": ("x",), "z": ("y",), "w": ("x",)}
try:
    graph.topological_order(cycle)
except ValueError as exc:
    print(f"    LOG (위상 정렬)       → ValueError: {exc}")
    print("                            '부모가 먼저' 인 순서 자체가 존재하지 않는다 (서로가 서로의 부모)")
print(f"    ANCESTORS(x)          → {graph.ancestors(cycle, 'x')}   ← seen 덕분에 멈추긴 하지만, z·y 는 x 의 조상이면서 동시에 자손")
print(f"    is_ancestor(x, y) = {graph.is_ancestor(cycle, 'x', 'y')}, is_ancestor(y, x) = {graph.is_ancestor(cycle, 'y', 'x')}"
      "   ← 둘 다 True → MERGE 가 양쪽 다 'Already up to date'")
steps, node = 0, "x"
while steps < 10_000:            # 방문 집합 없이 부모만 따라가면?
    node = cycle[node][0]
    steps += 1
print(f"    방문 집합 없이 부모 따라가기 → {steps:,} 걸음 뒤에도 안 끝남 (끊어서 멈춤) = 무한 루프")
print("    → 사이클이 있으면 '이력' 이 성립하지 않는다: 순서·조상·병합 판단이 전부 깨진다")

# ─────────────────────────────────────────────────────────────────────
section("3-2. LOG 의 '부모가 먼저' — Kahn 위상 정렬을 한 걸음씩")
repo, _ = build_diamond()
pm = repo.parents_map()
seq = {h: c.seq for h, c in repo.store._commits.items()}
children = graph.build_children(pm)
pending = {h: len(p) for h, p in pm.items()}
print("\n  '아직 안 나온 부모 수' 가 0 인 커밋만 준비됨(최소 힙, 동률은 생성 순번)에 들어간다")
ready = MinHeap(less=lambda a, b: a[0] < b[0])
for h, n in pending.items():
    if n == 0:
        ready.push((seq[h], h))
step = 0
while len(ready):
    _, h = ready.pop()
    step += 1
    newly = []
    for child in children[h]:
        pending[child] -= 1
        if pending[child] == 0:
            ready.push((seq[child], child))
            newly.append(label(child))
        else:
            newly.append(f"{label(child)} 남은 부모 {pending[child]}")
    print(f"    {step}. 출력 {label(h):<14} → 자식: {', '.join(newly) or '-'}")
print("    → M1 은 P·L 둘 다 나온 뒤, M2 는 M1·F 둘 다 나온 뒤에야 준비된다")

print("\n  비교: 시각으로 정렬하면? — 시계가 틀린 커밋 하나로 깨진다")
repo.commit("Commit from a skewed clock", timestamp=datetime(2025, 3, 10, 8, 0, 0))
by_time = ALGORITHMS["merge"](repo.store.all(), key=lambda c: c.timestamp)
pos = {c.hash: i for i, c in enumerate(by_time)}
broken = [(c.hash, p) for c in by_time for p in c.parents if pos[p] > pos[c.hash]]
print(f"    시각순 첫 커밋: {by_time[0].message!r} ({by_time[0].time_str()})")
print(f"    부모보다 먼저 나온 자식: {len(broken)}건 → {broken}")
topo = repo.log()
tpos = {c.hash: i for i, c in enumerate(topo)}
print(f"    LOG(위상 정렬)에서는: {sum(1 for c in topo for p in c.parents if tpos[p] > tpos[c.hash])}건")

# ─────────────────────────────────────────────────────────────────────
section("3-3. PATH — 왜 BFS 이고, 왜 간선을 무방향으로 보나")
repo, _ = build_diamond()
pm = repo.parents_map()
adj = graph.undirected_adjacency(pm)
dist = graph.bfs_distances(adj, "7333cf5")
print("\n  BFS 는 '가까운 것부터 한 겹씩' — P(7333cf5) 에서 잰 거리 층:")
layers = {}
for h, d in dist.items():
    layers.setdefault(d, []).append(label(h))
for d in range(len(layers)):
    print(f"    {d}칸: {', '.join(layers[d])}")
print("    → 간선 가중치가 모두 1 이면 처음 닿은 거리가 곧 최단 거리")


def ascending(values):
    """이웃 순서를 고정 (set 순회 순서는 실행마다 다르다). sorted 금지라 선택 정렬."""
    values = list(values)
    for i in range(len(values)):
        m = i
        for j in range(i + 1, len(values)):
            if values[j] < values[m]:
                m = j
        values[i], values[m] = values[m], values[i]
    return values


def dfs_first_path(start, goal):
    """비교용: 스택(DFS)으로 처음 찾은 경로. 이웃은 작은 hash 부터 쌓는다 → 큰 hash 부터 파고든다."""
    stack, seen = [(start, [start])], set()
    while stack:
        node, path = stack.pop()
        if node == goal:
            return path
        if node in seen:
            continue
        seen.add(node)
        for nb in ascending(adj[node]):
            stack.append((nb, path + [nb]))
    return None


dfs = dfs_first_path("7333cf5", "4280179")
bfs = graph.shortest_path(pm, "7333cf5", "4280179")
print(f"\n  P → A (바로 부모!)")
print(f"    DFS 가 처음 찾은 길: {' → '.join(label(h) for h in dfs)}  ({len(dfs) - 1}칸)")
print(f"    BFS 최단 경로     : {' → '.join(label(h) for h in bfs)}  ({len(bfs) - 1}칸)")
print("    DFS 는 한 갈래를 끝까지 판 뒤에야 돌아온다 — '찾기' 는 되지만 '최단' 은 보장 못 한다")


def directed_reachable(start, goal):
    """부모 방향으로만 걸을 때 goal 에 닿나."""
    return goal == start or goal in graph.ancestors(pm, start)


print("\n  무방향인 이유 — 부모 방향(화살표대로)으로만 걸으면:")
for a, b in [("8ff2dea", "4280179"), ("4280179", "8ff2dea"), ("8ff2dea", "7333cf5")]:
    path = graph.shortest_path(pm, a, b)
    print(f"    {label(a):>12} → {label(b):<12} 부모 방향만: {'닿음' if directed_reachable(a, b) else 'No path':<8}"
          f"  무방향: {len(path) - 1}칸")
print("    → 부모 방향만 허용하면 '조상으로 올라가기' 만 된다. 형제 브랜치(F·P) 끼리는 영원히 No path.")
print("      두 커밋이 '얼마나 떨어져 있나' 는 공통 조상을 거쳐 올라갔다 내려오는 거리 → 무방향")

# ─────────────────────────────────────────────────────────────────────
section("3-4. 정렬 4종 — 평균/최악 복잡도와 안정성을 '비교 횟수' 로 확인")


class Counted:
    """비교할 때마다 숫자를 세는 키 (시간은 기계마다 다르지만 비교 횟수는 같다)."""
    count = 0

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        Counted.count += 1
        return self.v < other.v

    def __gt__(self, other):
        Counted.count += 1
        return self.v > other.v


def comparisons(algo, values):
    Counted.count = 0
    ALGORITHMS[algo]([Counted(v) for v in values], key=lambda c: c)
    return Counted.count


rng = random.Random(0)
print(f"\n  {'':<11}{'random n=1000':>15}{'random n=2000':>15}{'2배 →':>8}{'sorted n=2000':>15}   이론(평균/최악) · 안정")
theory = {"merge": "n log n / n log n · ✔", "quick": "n log n / n²      · ✘",
          "heap": "n log n / n log n · ✘", "insertion": "n²      / n²      · ✔ (정렬 입력이면 n)"}
for algo in ALGORITHMS:
    c1 = comparisons(algo, [rng.random() for _ in range(1000)])
    c2 = comparisons(algo, [rng.random() for _ in range(2000)])
    cs = comparisons(algo, list(range(2000)))
    print(f"  {algo:<11}{c1:>15,}{c2:>15,}{c2 / c1:>7.1f}x{cs:>15,}   {theory[algo]}")
print("  → n 이 2배일 때 n log n 은 약 2.2배, n² 은 4배. 삽입 정렬은 정렬된 입력에서 n-1 번으로 끝난다")

print("\n  안정성: 위상 순서로 놓인 커밋을 작성자로 정렬 (번호 = 원래 순서)")
commits = [(1, "Ben"), (2, "Ari"), (3, "Ben"), (4, "Ari"), (5, "Ben"), (6, "Ari")]
for algo in ALGORITHMS:
    out = ALGORITHMS[algo](commits, key=lambda c: c[1])
    stable = all(not (a[1] == b[1] and a[0] > b[0]) for a, b in zip(out, out[1:]))
    print(f"    {algo:<10} {[n for n, _ in out]}  {'안정 ✔' if stable else '순서 섞임 ✘'}")
print("  → LOG --sort-by 는 병합 정렬: 같은 작성자 안에서 '부모가 먼저' 가 그대로 남는다")

# ─────────────────────────────────────────────────────────────────────
section("3-5. 역색인 — 순회 검색보다 빠른 이유")
print("\n  순회: 커밋 N 개의 메시지를 전부 쪼개 비교 → O(N × L)")
print("  역색인: 단어 → [hash, ...] 해시맵에서 한 번 찾고 결과 k 개만 꺼냄 → O(1) + O(k), N 과 무관")
print(f"\n  {'N':>8}{'k':>5}{'순회: 본 토큰 수':>16}{'색인: 본 항목 수':>16}{'순회 ms':>10}{'색인 ms':>10}")
words = "add fix update remove signup cart cart user api test docs build cache bug page".split()
for n in (1_000, 10_000, 100_000):
    st, ix = CommitStore(), CommitIndex()
    r = random.Random(1)
    ts = datetime(2024, 1, 1)
    for i in range(n):
        msg = " ".join(r.choice(words) for _ in range(5)) + (" zebra" if i % 1000 == 0 else "")
        ix.add_commit(st.create(msg, "dev", ts))
    t0 = time.perf_counter()
    scanned, hits = 0, []
    for c in st.all():
        toks = tokenize(c.message)
        scanned += len(toks)
        if "zebra" in toks:
            hits.append(c.hash)
    t_scan = time.perf_counter() - t0
    t0 = time.perf_counter()
    found = ix.search_keyword("zebra")
    t_index = time.perf_counter() - t0
    assert found == hits
    print(f"  {n:>8,}{len(found):>5}{scanned:>16,}{len(found):>16,}{t_scan * 1000:>10.2f}{t_index * 1000:>10.4f}")
print("  → 순회는 N 에 비례해 늘고, 색인은 결과 수 k 만큼만 일한다. 대가: 커밋할 때 토큰 수만큼 미리 등록(O(m))")
