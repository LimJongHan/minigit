"""경로 탐색 방법을 대조하는 실험 스크립트. `python3 docs/graph_demo.py`

1. 다이아몬드 그래프에서 위상 정렬 · 최단 경로 · 조상
2. 방문 집합이 없으면 merge 다이아몬드를 쌓을 때 조상 출력이 2^n 으로 폭발하는 것
3. 사전순 최소 경로: 출발지 BFS(이웃 순서 무작위 / 정렬) vs 목적지 BFS + 욕심 대조
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from minigit import graph  # noqa: E402


def section(title):
    print(f"\n== {title} ==")


def demo_diamond():
    section("1. 다이아몬드: a <- b, a <- c, (c, b) <- d")
    d = {"a": (), "b": ("a",), "c": ("a",), "d": ("c", "b")}
    print("topological_order :", graph.topological_order(d))
    print("shortest_path d→a :", graph.shortest_path(d, "d", "a"))
    print("shortest_path b→c :", graph.shortest_path(d, "b", "c"))
    print("ancestors(d)      :", graph.ancestors(d, "d"))


def stacked_diamonds(n):
    """다이아몬드를 n 층 쌓은 그래프. 맨 아래 merge 커밋 하나에서 위로 2^n 갈래 길."""
    pm = {"r0": ()}
    for i in range(n):
        top, left, right, bottom = f"r{i}", f"L{i}", f"R{i}", f"r{i + 1}"
        pm[left] = (top,)
        pm[right] = (top,)
        pm[bottom] = (left, right)
    return pm, f"r{n}"


def ancestors_without_seen(pm, start):
    """방문 집합 없이 부모를 따라가며 '만난 횟수' 를 센다 (일부러 틀린 버전)."""
    count = 0
    stack = list(pm[start])
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(pm[node])
    return count


def demo_explosion():
    section("2. 방문 집합이 없을 때 — 다이아몬드 n 층")
    print(f"{'n':>3} {'실제 조상 수':>12} {'seen 없이 센 횟수':>18}")
    for n in (1, 2, 4, 8, 12, 16):
        pm, bottom = stacked_diamonds(n)
        real = len(graph.ancestors(pm, bottom))
        naive = ancestors_without_seen(pm, bottom)
        print(f"{n:>3} {real:>12} {naive:>18}")


def selection_sorted(values):
    """이웃 목록을 작은 순서로 (sorted 금지라 선택 정렬로)."""
    values = list(values)
    for i in range(len(values)):
        m = i
        for j in range(i + 1, len(values)):
            if values[j] < values[m]:
                m = j
        values[i], values[m] = values[m], values[i]
    return values


def source_bfs_path(pm, start, goal, sort_neighbors):
    """출발지에서 BFS 하며 '처음 발견한 부모(prev)' 를 기록하고 거꾸로 따라 경로를 만든다."""
    adj = graph.undirected_adjacency(pm)
    prev = {start: None}
    queue, head = [start], 0
    while head < len(queue):
        node = queue[head]
        head += 1
        neighbors = selection_sorted(adj[node]) if sort_neighbors else adj[node]
        for nb in neighbors:
            if nb not in prev:
                prev[nb] = node
                queue.append(nb)
    if goal not in prev:
        return None
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return path[::-1]


def random_dag(rng, n, merge_rate=0.5):
    pm, names = {}, []
    for i in range(n):
        name = f"{rng.randrange(16 ** 4):04x}{i:03d}"
        if i == 0 or rng.random() < 0.05:
            parents = ()
        elif i >= 2 and rng.random() < merge_rate:
            parents = tuple(rng.sample(names, 2))
        else:
            parents = (rng.choice(names),)
        pm[name] = parents
        names.append(name)
    return pm


def demo_three_methods(trials=3000):
    section("3. 사전순 최소 최단 경로 — 세 방법을 무작위 DAG 로 대조")
    rng = random.Random(11)
    wrong_unsorted = wrong_sorted = compared = 0
    example = None
    for _ in range(trials):
        pm = random_dag(rng, 9)
        nodes = list(pm)
        s, g = rng.choice(nodes), rng.choice(nodes)
        answer = graph.shortest_path(pm, s, g)  # 목적지 BFS + 욕심 (테스트에서 브루트포스와 대조됨)
        if answer is None:
            continue
        compared += 1
        a = source_bfs_path(pm, s, g, sort_neighbors=False)
        b = source_bfs_path(pm, s, g, sort_neighbors=True)
        if a != answer:
            wrong_unsorted += 1
            example = example or (s, g, a, answer)
        if b != answer:
            wrong_sorted += 1
    print(f"비교한 쌍            : {compared}")
    print(f"출발지 BFS (이웃 순서 아무렇게, set 순회): 틀림 {wrong_unsorted}")
    print(f"출발지 BFS (이웃을 작은 순서로)          : 틀림 {wrong_sorted}")
    print(f"목적지 BFS + 욕심 (minigit)              : 기준")
    if example:
        s, g, got, answer = example
        print(f"틀린 예: {s}→{g}  set 순서 결과 {'->'.join(got)}")
        print(f"                  정답         {'->'.join(answer)}")


if __name__ == "__main__":
    demo_diamond()
    demo_explosion()
    demo_three_methods()
