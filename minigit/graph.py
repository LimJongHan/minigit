"""커밋 그래프 알고리즘 — 위상 정렬, 무방향 최단 경로, 조상 탐색.

모든 함수는 그래프를 `parents_map: {hash: (부모 hash, ...)}` 딕셔너리로 받는다.
저장소 클래스와 떨어져 있어서, 손으로 만든 작은 그래프로도 바로 테스트할 수 있다.

V = 커밋 수, E = 부모 연결 수 (일반 커밋 1개, merge 커밋 2개 → E ≈ V).
"""

from .sorting import MinHeap


def build_children(parents_map):
    """부모 → 자식 역방향 인접 리스트. O(V + E)."""
    children = {node: [] for node in parents_map}
    for node, parents in parents_map.items():
        for parent in parents:
            children[parent].append(node)
    return children


# ================================================================ 위상 정렬 (LOG)
def topological_order(parents_map, priority=None):
    """부모가 항상 자식보다 먼저 나오는 순서 — Kahn 알고리즘. O((V + E) log V).

    1. 각 커밋의 '아직 출력 안 된 부모 수' 를 센다. (간선을 부모→자식으로 볼 때의 진입 차수.
       저장은 자식→부모라 저장 방향으로는 진출 차수다 — 같은 숫자를 다른 쪽에서 본 것.)
    2. 그 수가 0 인 커밋(= 부모가 전부 출력됨) 만 '준비됨' 에 넣는다.
    3. 준비된 것 중 하나를 출력하고, 그 자식들의 수를 1씩 줄인다. 0 이 되면 준비됨으로.

    '준비됨' 이 여러 개일 때 무엇을 먼저 낼지는 위상 정렬이 정해주지 않는다.
    `priority(hash)` 가 가장 작은 것을 먼저 꺼내도록 최소 힙을 쓴다(기본: hash 문자열).
    → 같은 그래프면 항상 같은 순서가 나온다(결정적).

    모든 노드를 내보내지 못하면 사이클이 있다는 뜻이므로 ValueError.
    """
    priority = priority or (lambda node: node)
    children = build_children(parents_map)
    pending = {node: len(parents) for node, parents in parents_map.items()}

    ready = MinHeap(less=lambda a, b: a[0] < b[0])
    for node, count in pending.items():
        if count == 0:
            ready.push((priority(node), node))

    order = []
    while len(ready):
        _, node = ready.pop()
        order.append(node)
        for child in children[node]:
            pending[child] -= 1
            if pending[child] == 0:
                ready.push((priority(child), child))

    if len(order) != len(parents_map):
        raise ValueError("cycle detected: commit graph is not a DAG")
    return order


# ============================================================ 최단 경로 (PATH)
def undirected_adjacency(parents_map):
    """커밋-부모 연결을 양방향 간선으로 본 인접 리스트. O(V + E)."""
    adjacency = {node: set() for node in parents_map}
    for node, parents in parents_map.items():
        for parent in parents:
            adjacency[node].add(parent)
            adjacency[parent].add(node)
    return adjacency


def bfs_distances(adjacency, source):
    """source 에서 각 노드까지의 간선 수. 도달 못 하면 딕셔너리에 없다. O(V + E).

    BFS 는 가까운 것부터 한 겹씩 넓혀가므로, 처음 방문할 때의 거리가 곧 최단 거리다
    (모든 간선 가중치가 1 일 때만 성립 — 가중치가 다르면 다익스트라가 필요).
    """
    dist = {source: 0}
    queue = [source]
    head = 0  # list.pop(0) 은 O(n) 이라 '읽을 위치' 만 앞으로 옮기는 큐로 쓴다
    while head < len(queue):
        node = queue[head]
        head += 1
        for neighbor in adjacency[node]:
            if neighbor not in dist:
                dist[neighbor] = dist[node] + 1
                queue.append(neighbor)
    return dist


def shortest_path(parents_map, start, goal):
    """무방향 최단 경로 중 `a->b->c` 문자열이 사전순 최소인 경로. 없으면 None.

    두 단계로 푼다. O(V + E) + 경로 길이 × 이웃 수.

    1. **goal 에서** BFS 를 돌려 모든 노드의 'goal 까지 남은 거리' 를 구한다.
    2. start 에서 출발해, 매 걸음 '남은 거리가 정확히 1 줄어드는 이웃' 중
       hash 가 가장 작은 것으로 간다.

    왜 2번의 욕심(greedy) 이 맞나: 최단 경로들은 모두 같은 길이이고, 문자열 사전순은
    앞 칸부터 hash 를 하나씩 비교한 순서와 같다. (hash 가 모두 7자라 자명하다. 길이가 달라도
    16진수 글자는 전부 구분자 '-'(0x2D) 보다 커서 결과는 같지만, 길이 고정으로 이 논증이 필요 없게 했다.)
    앞 칸에서 더 작은 것을 고르면 뒤가 어떻든 그 경로가 이긴다. 그리고 '남은 거리 -1' 인
    이웃만 고르면 그 이웃에서 goal 까지 최단 경로가 반드시 존재하므로 막다른 길이 없다.

    다른 정답 풀이: start 에서 BFS 하되 **이웃을 작은 순서로 방문**하며 처음 발견한 부모를
    기록해도 된다(같은 층 안의 큐 순서가 곧 경로의 사전순이 되기 때문). 다만 노드마다 이웃
    정렬이 필요하다. 이웃 순서를 정하지 않으면(set 순회) 최단이지만 사전순이 틀린다 —
    docs/graph_demo.py 가 무작위 DAG 로 세 방법을 대조한다.
    """
    if start not in parents_map or goal not in parents_map:
        raise KeyError(start if start not in parents_map else goal)
    adjacency = undirected_adjacency(parents_map)
    remaining = bfs_distances(adjacency, goal)
    if start not in remaining:
        return None

    path = [start]
    current = start
    while current != goal:
        step = remaining[current] - 1
        best = None
        for neighbor in adjacency[current]:
            if remaining.get(neighbor) == step and (best is None or neighbor < best):
                best = neighbor
        path.append(best)
        current = best
    return path


# ============================================================== 조상 (ANCESTORS)
def ancestors(parents_map, start):
    """start 에서 부모 방향으로 도달 가능한 모든 커밋(자기 자신 제외). O(V + E).

    BFS + 방문 집합. merge 커밋 때문에 같은 조상에 두 갈래로 도달할 수 있는데,
    방문 집합이 없으면 그 조상(과 그 위 전부)이 중복 출력된다.
    결과는 가까운 세대부터(BFS 순서), 같은 세대 안에서는 parents 에 적힌 순서.
    """
    if start not in parents_map:
        raise KeyError(start)
    seen = {start}
    order = []
    queue = [start]
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for parent in parents_map[node]:
            if parent not in seen:
                seen.add(parent)
                order.append(parent)
                queue.append(parent)
    return order


def is_ancestor(parents_map, maybe_ancestor, node):
    """maybe_ancestor 가 node 자신이거나 node 의 조상이면 True. (merge 판단용)"""
    if maybe_ancestor == node:
        return True
    return maybe_ancestor in set(ancestors(parents_map, node))
