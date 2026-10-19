"""가정 시연 — '만약 ~라면' 질문 4개를 실제로 바꿔서 돌려 본다.

    python3 demo/whatif.py

4-1 커밋 수가 10배씩 늘면 어디가 병목인가 (실측) + 개선안 세 개를 직접 돌려 같은 답인지 확인
4-2 PATH 를 '부모 방향만' 으로 바꾸면 결과가 어떻게 달라지고 무엇을 고쳐야 하나
4-3 LOG --sort-by=author 가 '부모-자식 선후도 유지' 로 강화되면
4-4 hash 를 카운터 / 난수 / 내용 기반으로 만들 때 테스트·재현성·디버깅
"""

import random
import secrets
import time
from datetime import datetime, timedelta

from scenario import StepClock, build_diamond, label, section

from minigit import MiniGitCLI, Repository, graph
from minigit.index import normalize_author
from minigit.sorting import ALGORITHMS


def best_ms(fn, repeat=3):
    best = float("inf")
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best * 1000


def build_big(n):
    """main 줄기 + 20번째마다 10칸 전 커밋과 merge 하는 이력. 작성자 5명."""
    repo = Repository(clock=StepClock(step=timedelta(minutes=1)))
    repo.init("dev0")
    words = "add fix update remove signup cart cart user api test".split()
    rng = random.Random(0)
    hashes = []
    for i in range(n):
        repo.user = f"dev{i % 5}"
        parents = None
        if i >= 20 and i % 20 == 0:
            parents = (hashes[-1], hashes[-10])
        msg = " ".join(rng.choice(words) for _ in range(4)) + (" zebra" if i % 1000 == 0 else "")
        hashes.append(repo.commit(msg, parents=parents).hash)
    return repo, hashes


# ─────────────────────────────────────────────────────────────────────
section("4-1. 커밋 수가 10배가 되면 — 명령별 실측 (ms, 3회 중 최솟값)")
rows = {}
sizes = (1_000, 10_000, 100_000)
for n in sizes:
    repo, hashes = build_big(n)
    if n == sizes[-1]:
        big_repo, big_hashes = repo, hashes      # 개선안 C 에서 다시 쓴다
    head, root = hashes[-1], hashes[0]
    t0 = time.perf_counter()
    for k in range(200):
        repo.commit(f"extra {k}")
    commit_ms = (time.perf_counter() - t0) * 1000 / 200
    head = repo.head_commit()
    rows[n] = {
        "COMMIT (1회)": commit_ms,
        "SEARCH zebra": best_ms(lambda: repo.search_keyword("zebra")),
        "parents_map() 만": best_ms(repo.parents_map),
        "ANCESTORS HEAD": best_ms(lambda: repo.ancestors(head)),
        "MERGE 판단(is_ancestor)": best_ms(lambda: graph.is_ancestor(repo.parents_map(), root, head)),
        "PATH root→HEAD": best_ms(lambda: repo.path(root, head)),
        "LOG": best_ms(repo.log),
        "LOG --sort-by=author": best_ms(lambda: repo.log(sort_by="author")),
    }
print(f"\n  {'명령':<26}" + "".join(f"{f'V={n:,}':>13}" for n in sizes) + f"{'10배당':>10}")
for name in rows[sizes[0]]:
    vals = [rows[n][name] for n in sizes]
    ratio = (vals[2] / vals[0]) ** 0.5 if vals[0] > 0 else 0
    print(f"  {name:<26}" + "".join(f"{v:>13.3f}" for v in vals) + f"{ratio:>9.1f}x")
print("""
  읽는 법: '10배당' 이 1x 면 커밋 수와 무관, 10x 면 비례(O(V)), 10x 를 넘으면 V log V 이상
  ① COMMIT · SEARCH 는 커밋 수와 거의 무관 — 해시맵·역색인 덕
  ② 나머지는 전부 V 에 비례 이상. 공통 원인: 호출마다 parents_map() 을 새로 만든다 (그것만으로 O(V))
  ③ LOG 계열이 가장 무겁다 — 위상 정렬 O((V+E) log V) + (sort-by 면) 정렬 O(V log V) 를 매번 처음부터""")

print("  개선안 A — LOG: 지금 구현에서는 '위상 순서 = 생성 순서' 다")
repo, _ = build_big(10_000)
same = [c.hash for c in repo.log()] == [c.hash for c in repo.store.all()]
print(f"    repo.log() == store.all() (V=10,000) → {same}")
print("    이유: 부모는 항상 자식보다 먼저 만들어지고(seq 가 작다), Kahn 의 동률 규칙이 seq 라서")
print("          '가장 작은 seq 인 미출력 커밋' 은 부모가 다 나왔으므로 항상 준비됨에 있다")
print(f"    → 정렬 없이 생성순 리스트를 그대로 내면 된다: {best_ms(repo.log):.2f} ms → {best_ms(repo.store.all):.3f} ms")
print("    (단, 다른 저장소에서 커밋을 가져오는(fetch) 기능이 생기면 이 성질이 깨진다 → 그때는 Kahn 이 필요)")

print("\n  개선안 B — LOG --sort-by=author: author 역색인이 이미 '작성자별 · 생성순' 목록이다")
posting = repo.index.authors
authors = ALGORITHMS["merge"](posting.keys())           # 작성자 수(5명)만 정렬
via_index = [h for a in authors for h in posting.get(a)]
via_sort = [c.hash for c in repo.log(sort_by="author")]
print(f"    역색인 이어붙이기 == 지금 결과 → {via_index == via_sort}")
print(f"    {best_ms(lambda: repo.log(sort_by='author')):.2f} ms → "
      f"{best_ms(lambda: [h for a in ALGORITHMS['merge'](posting.keys()) for h in posting.get(a)]):.3f} ms"
      "   (V log V 정렬 → 작성자 A 명 정렬 A log A + 이어붙이기 V)")


def bfs_until(adjacency, goal, start=None):
    """bfs_distances 와 같되, start 를 '발견' 하는 순간 멈추는 버전 (minigit 코드는 그대로 두고 여기서만 실험).

    멈춰도 되는 이유: start 가 거리 d 로 처음 적히는 순간, 거리 d-1 이하인 노드는 이미 전부 적혀 있다(층 순서).
    욕심 걷기는 '남은 거리 < d' 인 노드만 묻기 때문에 표가 이미 충분하다.
    """
    dist, queue, head = {goal: 0}, [goal], 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for nb in adjacency[node]:
            if nb not in dist:
                dist[nb] = dist[node] + 1
                queue.append(nb)
                if nb == start:
                    return dist, head
    return dist, head


print(f"\n  개선안 C — PATH: 지금은 출발지가 3칸 앞이어도 목적지에서 BFS 를 끝까지 돈다 (V={len(big_repo.store):,})")
big_adj = graph.undirected_adjacency(big_repo.parents_map())
print(f"    (이웃 표를 만드는 데만 {best_ms(lambda: graph.undirected_adjacency(big_repo.parents_map())):.1f} ms — PATH 마다 매번)")
for name, a, b in [("가까움 (3칸 전)", big_hashes[-4], big_hashes[-1]), ("중간 (500 커밋 전)", big_hashes[-501], big_hashes[-1]),
                   ("먼 거리 (루트 ↔ 끝)", big_hashes[0], big_hashes[-1])]:
    full, n_full = bfs_until(big_adj, b)
    early, n_early = bfs_until(big_adj, b, start=a)
    same = graph.shortest_path(big_repo.parents_map(), a, b)
    print(f"    {name:<16} 끝까지: 꺼낸 노드 {n_full:>7,}개 {best_ms(lambda: bfs_until(big_adj, b)):7.2f} ms   "
          f"찾으면 멈춤: {n_early:>7,}개 {best_ms(lambda: bfs_until(big_adj, b, start=a)):7.3f} ms   "
          f"거리 {full[a]} = {early[a]}, 경로 길이 {len(same) - 1}")
print("    → 가까운 쌍은 수만 배 줄지만 먼 쌍·No path 는 그대로(닿지 않음은 다 봐야 확정). 이웃 표 재생성이 더 큰 몫이다")
print("""
  그 밖의 방향
    · parents_map / children / 이웃 목록을 커밋할 때 '덧붙여' 유지 → 매 호출 O(V) 재생성 제거
    · ANCESTORS · MERGE 판단: 세대 번호(루트 0, 자식 = 부모 최대 + 1) 를 저장해 두면
      '대상보다 세대가 낮은 쪽으로는 더 안 내려가도 된다' 로 가지치기 (진짜 Git 의 commit-graph)
    · PATH: 양쪽에서 동시에 BFS(양방향 BFS) → 탐색 반경이 절반씩 → 방문 노드 수 급감
    · 출력 자체가 V 줄 — LOG -n 처럼 개수 제한/페이지 단위 출력""")

# ─────────────────────────────────────────────────────────────────────
section("4-2. PATH 를 '부모 방향만' 으로 바꾸면")
repo, _ = build_diamond()
pm = repo.parents_map()


def directed_shortest_path(parents_map, start, goal):
    """부모 방향(자식 → 부모)으로만 걷는 최단 경로. 바뀐 곳 세 군데:

    ① 이웃 = 부모만 (undirected_adjacency 를 안 쓴다)
    ② '목적지까지 남은 거리' 표는 간선을 뒤집은 그래프(부모 → 자식)에서 goal 부터 BFS
    ③ start 가 goal 의 자손이 아니면 길이 없다 → None
    사전순 동률 깨기(남은 거리 −1 인 이웃 중 최소)는 그대로 쓴다.
    """
    children = graph.build_children(parents_map)
    remaining = graph.bfs_distances(children, goal)       # goal 의 자손들까지의 거리
    if start not in remaining:
        return None
    path, current = [start], start
    while current != goal:
        step = remaining[current] - 1
        best = None
        for parent in parents_map[current]:
            if remaining.get(parent) == step and (best is None or parent < best):
                best = parent
        path.append(best)
        current = best
    return path


def show(path):
    return "No path" if path is None else " → ".join(label(h) for h in path)


for a, b, why in [("a16e116", "4280179", "자손 → 조상"), ("4280179", "a16e116", "조상 → 자손"),
                  ("8ff2dea", "7333cf5", "형제 브랜치"), ("a16e116", "1cdd61f", "merge 두 갈래")]:
    print(f"\n  {label(a)} → {label(b)}   ({why})")
    print(f"    무방향 (지금) : {show(graph.shortest_path(pm, a, b))}")
    print(f"    부모 방향만   : {show(directed_shortest_path(pm, a, b))}")

print("\n  자손 → 조상인데도 답이 달라지는 경우 — 오래된 커밋을 merge 했을 때:")
old_merge = {"a": (), "b": ("a",), "c": ("b",), "d": ("c",), "m": ("d", "a")}
print(f"    {old_merge}   (m = merge(d, a))")
print(f"    무방향 (지금) d → a : {' → '.join(graph.shortest_path(old_merge, 'd', 'a'))}   (m 을 거쳐 2칸)")
print(f"    부모 방향만   d → a : {' → '.join(directed_shortest_path(old_merge, 'd', 'a'))}   (3칸)")
print("""
  달라지는 것
    · '조상으로 올라가기' 만 남는다 → 조상 → 자손, 형제 브랜치 사이는 전부 No path
    · 자손 → 조상 사이에서도 무방향은 '공통 자식(merge)을 거치는' 지름길을 쓸 수 있어서 길이가 달라진다 (위 d → a)
    · PATH a b 와 PATH b a 의 답이 달라진다 (대칭성이 사라짐)
  바꿔야 하는 구현
    ① undirected_adjacency → parents 만 이웃으로
    ② 남은 거리 표: goal 에서 BFS 하되 '자식 방향' 으로 (build_children 재사용)
    ③ 정의를 정해야 한다: 'a 가 b 의 자손일 때만' 인지, 안 되면 PATH b a 를 대신 시도할지
    ④ No path 가 흔해지므로 메시지를 'Not an ancestor' 처럼 구분할지 — 테스트도 대칭 가정을 빼야 한다""")

# ─────────────────────────────────────────────────────────────────────
section("4-3. LOG --sort-by=author 에 '부모가 먼저' 도 유지해야 한다면")
repo = Repository(clock=StepClock())
cli = MiniGitCLI(repo)
for line in ["init Ben", "commit 'R  root'", "branch side", "switch side", "init Ari",
             "commit 'A1 ari work'", "commit 'A2 ari work'", "switch main", "init Ben",
             "commit 'B1 ben work'", "commit 'B2 ben work'", "merge side 'M  merge'"]:
    cli.execute(line)
pm = repo.parents_map()
commits = {c.hash: c for c in repo.store.all()}


def violations(order):
    pos = {h: i for i, h in enumerate(order)}
    return [(commits[h].message[:2], commits[p].message[:2]) for h in order for p in pm[h] if pos[p] > pos[h]]


def describe(order):
    return "  ".join(f"{commits[h].message[:2]}({commits[h].author[0]})" for h in order)


now = [c.hash for c in repo.log(sort_by="author")]
print("\n  이력:  R(Ben) ← A1(Ari) ← A2(Ari) ← M(Ben)")
print("         R(Ben) ← B1(Ben)   ← B2(Ben)   ← M")
print(f"\n  지금 (위상순서를 작성자로 안정 정렬) : {describe(now)}")
print(f"    부모보다 먼저 나온 자식: {violations(now)}   ← Ari 의 A1 이 부모 R 보다 앞")
seq = {h: c.seq for h, c in commits.items()}
strategy = graph.topological_order(pm, priority=lambda h: (commits[h].author.casefold(), seq[h]))
print(f"\n  전략: Kahn 위상 정렬의 동률 규칙을 (작성자, 생성순) 으로")
print(f"        graph.topological_order(pm, priority=lambda h: (author, seq))")
print(f"        결과: {describe(strategy)}")
print(f"    부모보다 먼저 나온 자식: {violations(strategy)}")
print("""
  왜 되나: '정렬 후 고치기' 가 아니라 '부모가 다 나온 커밋들 중에서만' 작성자 순으로 고른다
    → 관계(하드 조건)는 Kahn 이 지키고, 작성자 순(소프트 조건)은 동률 규칙이 최대한 따른다
    → R 은 혼자 준비됨이라 먼저, 그다음 A1·B1 중 Ari 가 먼저 → A1 · A2 를 다 낸 뒤 Ben 들
  새 알고리즘이 필요 없다 — LOG 와 같은 함수에 우선순위만 바꿔 넘긴다 (O((V+E) log V))""")

# ─────────────────────────────────────────────────────────────────────
section("4-4. hash 를 카운터 / 난수 / 내용 기반으로 만들면 — 같은 시나리오를 두 번 실행")


def run_session(make_hash):
    """커밋 3개 이력을 만들고 hash 목록을 돌려준다."""
    hashes, counter = [], [0]
    for msg in ("Set up project", "Add signup", "Add cart"):
        counter[0] += 1
        hashes.append(make_hash(msg, hashes[-1] if hashes else "", counter[0]))
    return hashes


def counter_hash(msg, parent, n):
    return f"{n:07x}"


def random_hash(msg, parent, n):
    return secrets.token_hex(4)[:7]


seeded = random.Random(42)


def seeded_random_hash(msg, parent, n):
    return f"{seeded.getrandbits(28):07x}"


def content_hash_with(clock):
    import hashlib

    def make(msg, parent, n):
        return hashlib.sha1(f"{n}|{msg}|{clock().isoformat()}|{parent}".encode()).hexdigest()[:7]
    return make


print("\n  같은가   1번째 실행                  2번째 실행                  방식")
for name, factory in [
    ("카운터", lambda: counter_hash),
    ("난수 (secrets)", lambda: random_hash),
    ("난수 (시드 42 고정)", lambda: (seeded.seed(42), seeded_random_hash)[1]),
    ("내용 기반 + 실제 시계", lambda: content_hash_with(datetime.now)),
    ("내용 기반 + 고정 시계", lambda: content_hash_with(StepClock())),
]:
    r1 = run_session(factory())
    time.sleep(0.002)
    r2 = run_session(factory())
    print(f"    {'✔' if r1 == r2 else '✘'}     {' '.join(r1)}     {' '.join(r2)}     {name}")
print("""
  카운터
    테스트: 기대값에 hash 를 그대로 적는다 · 재현성: 항상 같다 · 디버깅: 순서가 보인다(7번째 커밋)
    단점: 다른 저장소와 번호가 겹친다(합칠 수 없다) · 내용과 무관해 위조를 감지 못 한다
  난수
    테스트: 기대값에 hash 를 적을 수 없다 → 시드를 주입해야 재현된다 (위 '시드 42 고정' 줄)
    디버깅: 두 번 돌린 로그를 hash 로 대조할 수 없다 · 유일성: 충돌 확인 루프가 여전히 필요
  내용 기반 (지금)
    재현성: 입력(시각 포함)이 같으면 같다 → 시계를 주입하면 테스트에 hash 를 적을 수 있다
    장점: 재료(순번·작성자·메시지·시각·부모)가 같으면 같은 id, 부모가 바뀌면 hash 가 바뀐다(위조 감지)
    단점: 7자로 자르면 충돌이 0 이 아니다 → 확인 루프 + 공간 고갈 가드(RuntimeError)
  → 이 프로젝트가 테스트에서 FakeClock 을, 시연에서 --fixed-clock 을 쓰는 이유가 바로 '내용 기반 + 실제 시계' 줄이다""")
