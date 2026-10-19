"""README 설명 그림 생성기 → docs/*.png

실행: python3 docs/make_figures.py

그림 속 값은 손으로 적지 않는다. demo/features.txt 를 실제로 재생해 만든 저장소와
minigit 의 함수(topological_order · bfs_distances · shortest_path · ancestors · 역색인)를 돌린 결과로 채운다.
코드나 시연 스크립트가 바뀌면 다시 돌리면 된다.

  commit-graph.png     커밋 그래프 — 별명(A·L·P…) · hash · 생성 순서 · 브랜치 · 시계 틀린 커밋 · 끊긴 docs
  log-orders.png       LOG / --sort-by=date / --sort-by=author 출력 순서 비교
  kahn-steps.png       LOG 의 위상 정렬(Kahn)을 한 단계씩
  path-bfs.png         PATH P → F: ① 목적지에서 BFS 로 남은 거리 → ② 남은 거리 -1 이웃 중 최소 hash
  ancestors-seen.png   ANCESTORS: BFS 순서와 방문 집합(seen)이 건너뛰는 간선 + seen 이 없을 때의 폭발
  inverted-index.png   역색인: 메시지 → 토큰 → posting, 순회 검색과 일한 양 비교
  architecture.png     모듈 구조와 명령 → 알고리즘 연결
"""

import os
import random
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs"))

import main  # noqa: E402
from graph_demo import ancestors_without_seen, stacked_diamonds  # noqa: E402
from minigit import MiniGitCLI, Repository, graph  # noqa: E402
from minigit.commit import CommitStore  # noqa: E402
from minigit.index import CommitIndex, tokenize  # noqa: E402

font_manager.fontManager.addfont("/System/Library/Fonts/AppleSDGothicNeo.ttc")
plt.rcParams["font.family"] = "Apple SD Gothic Neo"
MONO = "Menlo"
DPI = 130

INK, MUTED, FAINT, LINE = "#1f2328", "#57606a", "#d0d7de", "#8c959f"
AUTHOR = {"Ari": ("#2f6fb3", "#dbe9f7"), "Ben": ("#c4610f", "#fde7d2")}
GOOD, BAD, READY = "#1a7f37", "#cf222e", "#bf8700"
LAYER = ["#0b3d2e", "#1a7f37", "#4ac26b", "#aceebb"]          # 남은 거리 0 → 3

# ── 시연 재생 ────────────────────────────────────────────────────────
repo = Repository(clock=main.StepClock())
cli = MiniGitCLI(repo)
with open(os.path.join(ROOT, "demo", "features.txt"), encoding="utf-8") as f:
    for raw in f:
        line = raw.strip()
        if line and not line.startswith("#") and line.lower() not in ("exit", "quit"):
            cli.execute(line)
C = {c.hash: c for c in repo.store.all()}
ORDER = list(C)
ALIAS = dict(zip(ORDER, ["A", "L", "P", "M1", "F", "M2", "S", "D"]))
H = {v: k for k, v in ALIAS.items()}
LANE = {"A": 2.0, "L": 0.75, "P": 2.0, "M1": 2.0, "F": 0.75, "M2": 2.0, "S": 2.0, "D": -1.25}
POS = {h: (i * 2.25, LANE[ALIAS[h]]) for i, h in enumerate(ORDER)}
PM_ALL = repo.parents_map()
MAIN7 = [h for h in ORDER if ALIAS[h] != "D"]                   # docs 를 뺀 연결 덩어리
PM = {h: PM_ALL[h] for h in MAIN7}
EDGES = [(h, p) for h in MAIN7 for p in PM[h]]
SEQ = {h: C[h].seq for h in ORDER}


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"  ✓ docs/{name}")


def frame(ax, xlim, ylim):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")


def arrow(ax, child, parent, color=LINE, lw=1.6, style="-", z=1, w=1.25, scale=1.0):
    half = w / 2 + 0.06                                  # 박스 가장자리 바로 바깥 → 화살촉이 보인다
    (x1, y1), (x2, y2) = POS[child], POS[parent]
    rad = 0.0 if y1 == y2 else (0.18 if y1 > y2 else -0.18)
    ax.add_patch(FancyArrowPatch((x1 - half, y1), (x2 + half, y2), arrowstyle="-|>",
                                 mutation_scale=13 * scale, color=color, lw=lw, linestyle=style, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))


def box(ax, h, fill=None, edge=None, ring=None, ring_w=3.0, w=1.25, hgt=0.72, sub=None, sub_color=MUTED,
        badge=None, dim=False, alias_color=None, show_hash=True, hash_color=MUTED):
    x, y = POS[h]
    e, fl = AUTHOR[C[h].author]
    if dim:
        e, fl = FAINT, "#f6f8fa"
    merge = len(C[h].parents) > 1
    ax.add_patch(FancyBboxPatch((x - w / 2, y - hgt / 2), w, hgt, boxstyle="round,pad=0.02,rounding_size=0.1",
                                fc=fill or fl, ec=ring or edge or e, zorder=3,
                                lw=ring_w if ring else (2.2 if merge else 1.3)))
    ax.text(x, y + (0.1 if show_hash else 0), ALIAS[h], fontsize=14, fontweight="bold", ha="center", va="center",
            zorder=4, color=alias_color or (MUTED if dim else e))
    if show_hash:
        ax.text(x, y - 0.19, h, fontsize=7.2, family=MONO, ha="center", va="center", zorder=4, color=hash_color)
    if sub:
        ax.text(x, y - hgt / 2 - 0.12, sub, fontsize=8.5, ha="center", va="top", color=sub_color, zorder=4)
    if badge:
        bx, by = x + w / 2 - 0.02, y + hgt / 2
        ax.add_patch(plt.Circle((bx, by), 0.17, color=badge[1], zorder=5))
        ax.text(bx, by, str(badge[0]), color="white", fontsize=8.5, fontweight="bold",
                ha="center", va="center", zorder=6)


def lanes(ax, xmax, docs=False):
    names = [("main", 2.0), ("feature", 0.75)] + ([("docs\n(orphan)", -1.25)] if docs else [])
    for name, y in names:
        ax.axhline(y, color="#eef1f4", lw=16, zorder=0)
        ax.text(-1.0, y, name, fontsize=10.5, fontweight="bold", color=MUTED, ha="right", va="center")


def finish(fig, axes, text, sub, name):
    """그림을 다 그린 뒤, 실제 그려진 axes 바로 위에 제목을 놓고 저장한다 (aspect 때문에 생기는 빈 공간 제거)."""
    fig.canvas.draw()
    top = max(a.get_position().y1 for a in axes)
    left = min(a.get_position().x0 for a in axes)
    inch = 1 / fig.get_figheight()
    fig.text(left, top + 0.78 * inch, text, fontsize=17, fontweight="bold", va="bottom")
    fig.text(left, top + 0.42 * inch, sub, fontsize=10.5, color=MUTED, va="bottom")
    save(fig, name)




def columns(ax, x_list, y, values, aligns, fontsize=10.5, color=INK, bold=False, transform=None):
    """표를 칸 단위로 찍는다 (한글이 섞인 고정폭 정렬은 Menlo 로 안 되므로 칸마다 따로 놓는다)."""
    for x, v, ha in zip(x_list, values, aligns):
        ax.text(x, y, v, fontsize=fontsize, ha=ha, va="top", color=color,
                fontweight="bold" if bold else None, transform=transform or ax.transData)


# ══════════════════════════════════════════════════════════════════════
# 1. 커밋 그래프
def fig_commit_graph():
    fig, ax = plt.subplots(figsize=(17, 6.3))
    lanes(ax, 17, docs=True)
    W = 1.55
    for child, parent in EDGES:
        arrow(ax, child, parent, w=W)
    notes = {"A": "Set up project\nAri 09:00", "L": "Add signup feature\nAri 09:15",
             "P": "Add cart feature\nAri 09:30", "M1": "merge(P, L)\nAri 09:45",
             "F": "Fix SIGNUP, signout bug\nBen 10:00", "M2": "merge(M1, F)\nBen 10:15",
             "S": "시계가 틀린 커밋\nBen 08:00 ← 부모보다 과거!", "D": "Docs root\nBen 10:30"}
    for i, h in enumerate(ORDER):
        box(ax, h, w=W, hgt=0.78, sub=notes[ALIAS[h]], sub_color=BAD if ALIAS[h] == "S" else MUTED,
            badge=(i + 1, "#6e7781"))
    tags = {"S": ("HEAD → main", INK), "F": ("feature", MUTED), "D": ("docs", MUTED)}
    for a, (text, color) in tags.items():
        x, y = POS[H[a]]
        ax.text(x, y + 0.72, text, fontsize=9, color="white", ha="center", va="center", fontweight="bold", zorder=6,
                bbox=dict(boxstyle="round,pad=0.28", fc=color, ec="none"))
    mx = (POS[H["M1"]][0] + POS[H["F"]][0]) / 2
    ax.plot([mx, mx], [-0.35, 2.75], color=AUTHOR["Ben"][0], lw=1.1, ls=(0, (2, 3)), zorder=0)
    ax.text(mx, 2.82, 'init "Ben" — 여기부터 작성자 Ben', fontsize=9.5, color=AUTHOR["Ben"][0], ha="center", va="bottom")
    ax.plot([-0.9, 17], [-0.4, -0.4], color=LINE, lw=1, ls=(0, (4, 4)), zorder=0)
    ax.text(13.9, -1.25, "docs 는 부모 없는 새 루트 → 위쪽과 잇는 선이 없다  →  path docs main = No path",
            fontsize=10, color=BAD, ha="right", va="center")
    frame(ax, (-2.2, 17), (-2.1, 3.15))
    finish(fig, [ax], "커밋 그래프 — demo/features.txt 가 만드는 이력",
           "화살표 = 자식 → 부모  ·  파랑 Ari / 주황 Ben  ·  굵은 테두리 = merge(부모 2개)  ·  ①~⑧ = 만들어진 순서(seq)",
           "commit-graph.png")


# ══════════════════════════════════════════════════════════════════════
# 2. LOG 출력 순서
def chips(ax, y, seq, label, note, divider=False):
    ax.text(-0.5, y, label, fontsize=12, fontweight="bold", family=MONO, ha="right", va="center")
    for i, h in enumerate(seq):
        cx = 0.6 + i * 1.5
        e, fl = AUTHOR[C[h].author]
        skew = ALIAS[h] == "S"
        ax.add_patch(FancyBboxPatch((cx - 0.58, y - 0.36), 1.16, 0.72, boxstyle="round,pad=0.02,rounding_size=0.1",
                                    fc=fl, ec=BAD if skew else e, lw=2.4 if skew else 1.3, zorder=3))
        ax.text(cx, y + 0.1, ALIAS[h], fontsize=13, fontweight="bold", color=e, ha="center", va="center", zorder=4)
        ax.text(cx, y - 0.19, f"{C[h].timestamp:%H:%M}", fontsize=8, color=BAD if skew else MUTED,
                ha="center", va="center", zorder=4)
        if i:
            ax.annotate("", (cx - 0.6, y), (cx - 0.9, y), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.1))
        if divider and i and C[seq[i - 1]].author != C[h].author:
            ax.plot([cx - 0.75] * 2, [y - 0.5, y + 0.5], color=INK, lw=2.2)
    ax.text(0.02, y - 0.62, note, fontsize=10, color=MUTED, va="top")


def fig_log_orders():
    fig, ax = plt.subplots(figsize=(13, 6.2))
    topo = [c.hash for c in repo.log()]
    date = [c.hash for c in repo.log(sort_by="date")]
    auth = [c.hash for c in repo.log(sort_by="author")]
    chips(ax, 0, topo, "LOG", "위상 정렬(Kahn) — 부모가 항상 먼저. S 는 08:00 인데도 부모 M2 뒤 → 시각이 아니라 관계로 정렬")
    chips(ax, -2.0, date, "--sort-by=date", "시각순 — 08:00 의 S 가 맨 앞으로. 부모(M2)보다 자식(S)이 먼저 나온다")
    chips(ax, -4.0, auth, "--sort-by=author",
          "작성자순(안정 병합 정렬, 입력 = 위상 순서) — Ari | Ben 으로 묶이고, 묶음 안은 위상 순서 그대로", divider=True)
    frame(ax, (-3.4, 12.0), (-5.0, 0.55))
    finish(fig, [ax], "LOG 세 가지 — 같은 커밋, 다른 순서",
           "칸 아래 = timestamp  ·  빨간 테두리 S = 08:00 으로 찍힌 '시계가 틀린 커밋' (부모 M2 는 10:15)",
           "log-orders.png")


# ══════════════════════════════════════════════════════════════════════
# 3. Kahn 단계별
def sorted_by_seq(hs):
    """준비됨 목록을 seq 순으로 (sorted 금지 — 삽입 정렬, 원소가 많아야 3개)."""
    result = []
    for h in hs:
        i = len(result)
        while i > 0 and SEQ[result[i - 1]] > SEQ[h]:
            i -= 1
        result.insert(i, h)
    return result


def kahn_states():
    children = graph.build_children(PM)
    pending = {h: len(p) for h, p in PM.items()}
    ready = sorted_by_seq([h for h, n in pending.items() if n == 0])
    out, states = [], [([], list(ready), dict(pending), None)]
    while ready:
        h = ready.pop(0)
        out.append(h)
        for ch in children[h]:
            pending[ch] -= 1
            if pending[ch] == 0:
                ready.append(ch)
        ready = sorted_by_seq(ready)
        states.append((list(out), list(ready), dict(pending), h))
    return states


def fig_kahn():
    states = kahn_states()
    assert states[-1][0] == [c.hash for c in repo.log() if c.hash in PM]
    fig, axes = plt.subplots(4, 2, figsize=(17, 11.6))
    W = 1.0
    for k, (axk, (out, ready, pending, popped)) in enumerate(zip(axes.T.flat, states)):
        for child, parent in EDGES:
            done = child in out and parent in out
            arrow(axk, child, parent, color=GOOD if done else FAINT, lw=2 if done else 1.1, w=W)
        for h in MAIN7:
            if h in out:
                box(axk, h, w=W, hgt=0.62, show_hash=False, badge=(out.index(h) + 1, GOOD))
            elif h in ready:
                box(axk, h, w=W, hgt=0.62, show_hash=False, ring=READY, sub="준비됨", sub_color=READY)
            else:
                box(axk, h, w=W, hgt=0.62, show_hash=False, dim=True, sub=f"남은 부모 {pending[h]}")
        head = "시작" if popped is None else f"{k}단계 — {ALIAS[popped]} 출력"
        rd = ", ".join(ALIAS[h] for h in ready) or "없음 (끝)"
        axk.text(-0.6, 3.15, head, fontsize=13, fontweight="bold", va="bottom")
        axk.text(4.2, 3.15, f"준비됨: {rd}", fontsize=11, color=READY, va="bottom", fontweight="bold")
        frame(axk, (-0.8, 14.3), (-0.05, 3.7))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.01, wspace=0.06, hspace=0.06)
    finish(fig, list(axes.flat), "LOG = 위상 정렬(Kahn) 한 단계씩 — 왼쪽 위부터 아래로, 그다음 오른쪽 열",
           "회색 박스 아래 = 아직 안 나온 부모 수  ·  노란 테두리 = 준비됨(그 수가 0 → 최소 힙)  ·  초록 번호 = 출력 순서  ·  "
           "준비됨이 여럿이면 생성 순번(seq) 작은 것부터", "kahn-steps.png")


# ══════════════════════════════════════════════════════════════════════
# 4. PATH — BFS 거리 → 욕심 걷기
def fig_path():
    start, goal = H["P"], H["F"]
    adj = graph.undirected_adjacency(PM)
    remaining = graph.bfs_distances(adj, goal)
    path = graph.shortest_path(PM, start, goal)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(14, 9.0))
    # ① BFS
    for child, parent in EDGES:
        arrow(a1, child, parent, color=FAINT, lw=1.3)
    for h in MAIN7:
        d = remaining[h]
        box(a1, h, fill=LAYER[d], edge=LAYER[d], alias_color="white" if d < 2 else INK,
            hash_color="#e6f4ea" if d < 2 else MUTED, sub=f"남은 거리 {d}", sub_color=INK)
    x, y = POS[goal]
    a1.text(x, y + 0.58, "목적지 F — 여기서 BFS 시작", fontsize=10, ha="center", fontweight="bold")
    a1.text(-0.6, 3.72, "① bfs_distances(이웃, 목적지 F) — 걷기 전에 '남은 거리' 표를 다 채운다", fontsize=13.5,
            fontweight="bold", va="top")
    a1.text(-0.6, 3.3, "큐에서 꺼낸 노드의 이웃 중 아직 안 적힌 것에 '내 거리 + 1' 을 적는다.  F 0 → (M2, L) 1 → (M1, S, A) 2 → P 3\n"
            "한 층씩 넓어지므로 처음 적힌 값이 최단이다(간선 길이가 모두 1).  hash 비교는 없다 — 같은 층의 방문 순서는 set 순서라 "
            "실행마다 달라도 표는 같다.", fontsize=10, color=MUTED, va="top", linespacing=1.6)
    frame(a1, (-0.8, 14.4), (-0.1, 3.8))
    # ② 욕심 걷기
    path_edges = {frozenset(e) for e in zip(path, path[1:])}
    rejected, lines = [], []
    for cur, nxt in zip(path, path[1:]):
        step = remaining[cur] - 1
        cands = sorted_by_seq([nb for nb in adj[cur] if remaining.get(nb) == step])
        rejected += [(cur, nb) for nb in cands if nb != nxt]
        if len(cands) > 1:
            lines.append(f"{ALIAS[cur]}(남은 {remaining[cur]}) → 남은 {step} 인 이웃: "
                         + ", ".join(f"{ALIAS[c]} {c}" for c in cands) + f"   →  {ALIAS[nxt]}  ({nxt} 가 가장 작다)")
        else:
            lines.append(f"{ALIAS[cur]}(남은 {remaining[cur]}) → 남은 {step} 인 이웃: {ALIAS[nxt]} 하나   →  {ALIAS[nxt]}")
    for child, parent in EDGES:
        key = frozenset((child, parent))
        if key in path_edges:
            arrow(a2, child, parent, color=GOOD, lw=4, z=2)
        elif any(key == frozenset(r) for r in rejected):
            arrow(a2, child, parent, color=BAD, lw=2.4, style=(0, (3, 2)), z=2)
        else:
            arrow(a2, child, parent, color=FAINT, lw=1.2)
    for h in MAIN7:
        on = h in path or any(h == r[1] for r in rejected)
        badge = (path.index(h) + 1, GOOD) if h in path else None
        box(a2, h, dim=not on, badge=badge, sub=f"남은 {remaining[h]}", sub_color=INK if on else MUTED)
    a2.text(-0.6, 4.0, "② shortest_path — P 에서 한 걸음씩: 남은 거리가 정확히 1 줄어드는 이웃 중 hash 가 가장 작은 것",
            fontsize=13.5, fontweight="bold", va="top")
    a2.text(-0.6, 3.58, "\n".join(lines), fontsize=10.5, color=INK, va="top", linespacing=1.6)
    a2.text(14.2, -0.2, "결과  " + " → ".join(ALIAS[h] for h in path)
            + "      빨간 점선 = 같은 3칸이지만 두 번째 칸 hash(70cf…)가 커서 버린 길",
            fontsize=11, color=GOOD, ha="right", fontweight="bold")
    frame(a2, (-0.8, 14.4), (-0.45, 4.08))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.01, hspace=0.08)
    finish(fig, [a1, a2], "PATH P → F — 경로를 모아서 비교하지 않는다",
           "간선은 무방향(부모·자식 양쪽)  ·  ① 거리표 만들기 O(V+E) → ② 갈림길마다 그 자리의 이웃만 비교  ·  "
           "최단 경로가 몇 개든(2ⁿ 개여도) 비용이 늘지 않는다", "path-bfs.png")


# ══════════════════════════════════════════════════════════════════════
# 5. ANCESTORS — seen
def fig_ancestors():
    start = H["S"]
    order, discovered_by, skipped = [], {}, []
    seen, queue, head = {start}, [start], 0
    while head < len(queue):
        node = queue[head]
        head += 1
        for p in PM[node]:
            if p in seen:
                skipped.append((node, p))
            else:
                seen.add(p)
                order.append(p)
                discovered_by[p] = node
                queue.append(p)
    assert order == graph.ancestors(PM, start)
    fig = plt.figure(figsize=(19, 5.2))
    ax = fig.add_axes([0.0, 0.0, 0.66, 0.9])
    found = {frozenset((c, p)) for p, c in discovered_by.items()}
    skip = {frozenset(e) for e in skipped}
    for child, parent in EDGES:
        key = frozenset((child, parent))
        if key in found:
            arrow(ax, child, parent, color=GOOD, lw=3, z=2)
        elif key in skip:
            arrow(ax, child, parent, color=LINE, lw=1.6, style=(0, (2, 2)), z=2)
            (x1, y1), (x2, y2) = POS[child], POS[parent]
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.05, "× 이미 seen", fontsize=9, color=BAD, ha="center",
                    va="center", zorder=5, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
    for h in MAIN7:
        if h == start:
            box(ax, h, ring=INK, sub="시작 (HEAD)", sub_color=INK)
        else:
            box(ax, h, badge=(order.index(h) + 1, GOOD), sub=f"{ALIAS[discovered_by[h]]} 에서 발견")
    frame(ax, (-0.8, 14.5), (0.0, 2.6))
    ax2 = fig.add_axes([0.69, 0.0, 0.3, 0.9])
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.text(0, 0.98, "seen 이 없으면? — 다이아몬드를 n 층 쌓으면", fontsize=12.5, fontweight="bold", va="top")
    ax2.text(0, 0.88, "merge 마다 '두 갈래로 같은 조상에 닿음' 이 곱해진다", fontsize=10, color=MUTED, va="top")
    xs, al = [0.08, 0.5, 0.95], ["right", "right", "right"]
    columns(ax2, xs, 0.74, ["n", "진짜 조상 수", "seen 없이 센 횟수"], al, bold=True)
    for i, n in enumerate((1, 2, 4, 8, 12, 16)):
        pm, bottom = stacked_diamonds(n)
        real, naive = len(graph.ancestors(pm, bottom)), ancestors_without_seen(pm, bottom)
        columns(ax2, xs, 0.64 - i * 0.09, [str(n), f"{real:,}", f"{naive:,}"], al,
                color=BAD if naive > 1000 else INK)
    ax2.text(0, 0.04, "숫자: docs/graph_demo.py 와 같은 함수로 계산", fontsize=9, color=MUTED)
    finish(fig, [ax, ax2], "ANCESTORS HEAD(= S) — 부모 방향 BFS + 방문 집합(seen)",
           "초록 번호 = 출력 순서(가까운 세대부터)  ·  초록 화살표 = 처음 발견한 길  ·  회색 점선 = 이미 seen 이라 건너뛴 길  ·  "
           "seen 은 큐에 '넣을 때' 표시", "ancestors-seen.png")


# ══════════════════════════════════════════════════════════════════════
# 6. 역색인
def fig_index():
    idx = repo.index
    fig = plt.figure(figsize=(18, 8.2))
    ax = fig.add_axes([0.0, 0.3, 1.0, 0.62])
    ax.axis("off")
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 9)
    ax.text(0.2, 8.95, "커밋 (생성 순서)", fontsize=12.5, fontweight="bold", va="top")
    for i, h in enumerate(ORDER):
        y = 7.8 - i * 0.95
        e, fl = AUTHOR[C[h].author]
        hl = "signup" in tokenize(C[h].message)
        ax.add_patch(FancyBboxPatch((0.2, y - 0.36), 6.6, 0.72, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc=fl, ec=GOOD if hl else e, lw=2.6 if hl else 1.0))
        ax.text(0.45, y, ALIAS[h], fontsize=12, fontweight="bold", color=e, va="center")
        ax.text(1.1, y, h, fontsize=9, family=MONO, color=MUTED, va="center")
        msg = C[h].message if len(C[h].message) < 30 else C[h].message[:28] + "…"
        ax.text(2.4, y, msg, fontsize=10, va="center")
        ax.text(6.65, y, C[h].author, fontsize=9, color=e, va="center", ha="right")
    ax.annotate("", (8.3, 4.5), (7.0, 4.5), arrowprops=dict(arrowstyle="-|>", color=INK, lw=2))
    ax.text(7.65, 4.85, "tokenize", fontsize=10, ha="center", fontweight="bold")
    ax.text(7.65, 4.15, "'Fix SIGNUP, signout bug'\n→ fix · signup · signout · bug", fontsize=8.5, ha="center",
            va="top", color=MUTED)
    ax.text(8.6, 8.95, "keyword 역색인 (일부)", fontsize=12.5, fontweight="bold", va="top")
    for i, k in enumerate(["signup", "add", "feature", "fix", "signout", "merge", "commit", "docs"]):
        y = 7.8 - i * 0.95
        hl = k == "signup"
        ax.text(8.7, y, f"'{k}'", fontsize=11, family=MONO, va="center", color=GOOD if hl else INK,
                fontweight="bold" if hl else None)
        ax.text(10.1, y, "→  " + "  ".join(ALIAS[h] for h in idx.keywords.get(k)), fontsize=11, va="center",
                color=GOOD if hl else INK, fontweight="bold" if hl else None)
    ax.text(14.2, 8.95, "author 역색인", fontsize=12.5, fontweight="bold", va="top")
    for i, a in enumerate(idx.authors.keys()):
        y = 7.8 - i * 0.95
        ax.text(14.3, y, f"'{a}'", fontsize=11, family=MONO, va="center")
        ax.text(15.4, y, "→  " + "  ".join(ALIAS[h] for h in idx.authors.get(a)), fontsize=11, va="center")
    ax.text(14.2, 5.5, "search signup\n= 'signup' 줄 하나 꺼내기\n→ L, F (초록)", fontsize=11, color=GOOD, va="top",
            fontweight="bold", linespacing=1.5)
    ax.text(14.2, 3.4, "search \"fix bug\"\n= 'fix' 줄 ∩ 'bug' 줄 (AND)\n가장 짧은 목록을 기준으로", fontsize=10.5,
            va="top", linespacing=1.5)
    ax3 = fig.add_axes([0.0, 0.0, 1.0, 0.27])
    ax3.axis("off")
    ax3.set_xlim(0, 18)
    ax3.set_ylim(0, 1)
    words = "add fix update remove signup cart cart user api test docs build cache bug page".split()
    ax3.text(0.2, 0.98, "같은 검색 'zebra'(1,000개에 1번 나오는 단어)를 할 때 들여다본 양", fontsize=12.5,
             fontweight="bold", va="top")
    xs, al = [2.2, 5.4, 8.6], ["right", "right", "right"]
    columns(ax3, xs, 0.76, ["커밋 수 N", "순회: 본 토큰 수", "역색인: 본 항목 수"], al, bold=True)
    for i, n in enumerate((1_000, 10_000, 100_000)):
        st, ix = CommitStore(), CommitIndex()
        r = random.Random(1)
        for j in range(n):
            msg = " ".join(r.choice(words) for _ in range(5)) + (" zebra" if j % 1000 == 0 else "")
            ix.add_commit(st.create(msg, "dev", C[ORDER[0]].timestamp))
        scanned = sum(len(tokenize(c.message)) for c in st.all())
        columns(ax3, xs, 0.58 - i * 0.17, [f"{n:,}", f"{scanned:,}", f"{len(ix.search_keyword('zebra')):,}"], al)
    ax3.text(10.0, 0.76, "순회 = 모든 메시지를 쪼개 비교 → O(N × L), N 에 비례\n"
             "역색인 = 해시맵에서 키 한 번 + 결과 k 개 → O(1) + O(k), N 과 무관\n"
             "대가 = 커밋할 때 토큰 수 m 만큼 미리 등록 → O(m)", fontsize=11, va="top", linespacing=1.7)
    finish(fig, [ax], "SEARCH = 역색인 — 커밋할 때 미리 '단어 → 커밋 목록' 을 만들어 둔다",
           "토큰화: 소문자 + 공백 split + 양 끝 문장부호 제거 ('SIGNUP,' → 'signup')  ·  "
           "갱신 시점: Repository.commit() 안, 저장 직후 한 번", "inverted-index.png")


# ══════════════════════════════════════════════════════════════════════
# 7. 구조
def fig_architecture():
    fig, ax = plt.subplots(figsize=(17, 7.4))
    ax.axis("off")
    ax.set_xlim(0, 17)
    ax.set_ylim(0.8, 8.2)

    def card(x, y, w, h, name, head, body, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc="white", ec=color, lw=2))
        ax.text(x + 0.15, y + h - 0.2, name, fontsize=11.5, fontweight="bold", family=MONO, va="top", color=color)
        if head:
            ax.text(x + 0.15, y + h - 0.6, head, fontsize=10, fontweight="bold", va="top", color=color)
        ax.text(x + 0.15, y + h - (1.0 if head else 0.62), body, fontsize=9.4, va="top", linespacing=1.55, color=INK)

    def link(x1, y1, x2, y2):
        ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.5,
                                                            shrinkA=0, shrinkB=0))

    card(0.3, 6.7, 3.6, 1.3, "main.py", None, "REPL: 읽기 → 실행 → 출력 반복\n--fixed-clock: 시계 고정", MUTED)
    card(4.6, 6.7, 6.0, 1.3, "minigit/cli.py", None, "shlex 로 토큰 → 명령 표에서 고르기 → 출력 문자열\n"
         "표준 에러: Invalid args · Unknown branch / commit", MUTED)
    link(3.9, 7.35, 4.6, 7.35)
    card(0.3, 3.7, 10.3, 2.4, "minigit/repository.py", "명령의 '의미' — 상태 5개",
         "user        현재 작성자\nhead        현재 브랜치 '이름'\nbranches    이름 → hash (이름표 — 커밋을 복사하지 않음)\n"
         "store · index   CommitStore · CommitIndex", "#2f6fb3")
    link(7.6, 6.7, 7.6, 6.1)
    algo = [("commit.py", "Commit (frozen)\nCommitStore\nhash → Commit 해시맵\nSHA-1 7자 + nonce"),
            ("graph.py", "topological_order\nbfs_distances\nshortest_path\nancestors · is_ancestor"),
            ("sorting.py", "merge · quick\nheap · insertion\nMinHeap"),
            ("index.py", "tokenize\nkeyword → [hash]\nauthor → [hash]"),
            ("diff.py", "LCS 줄 비교\n(DIFF)")]
    wcard, gap = 1.94, 0.15
    for i, (name, body) in enumerate(algo):
        x = 0.3 + i * (wcard + gap)
        card(x, 1.0, wcard, 2.0, name, None, body, GOOD)
        link(5.45, 3.7, x + wcard / 2, 3.0)
    ax.text(11.3, 6.9, "명령 → 쓰는 알고리즘", fontsize=12.5, fontweight="bold", va="top")
    mapping = [("COMMIT", "store.create → 브랜치 전진\n→ index.add_commit"),
               ("LOG", "topological_order(priority=seq)"),
               ("LOG --sort-by", "위상 순서를 merge_sort — 안정"),
               ("PATH", "undirected_adjacency\n→ bfs_distances → 욕심 걷기"),
               ("ANCESTORS", "ancestors (BFS + seen)"),
               ("MERGE", "is_ancestor → 부모 2개 커밋"),
               ("SEARCH", "search_keyword / search_author")]
    y = 6.35
    for cmd, how in mapping:
        ax.text(11.35, y, cmd, fontsize=10, family=MONO, fontweight="bold", va="top")
        ax.text(13.45, y, how, fontsize=9.4, va="top", linespacing=1.4)
        y -= 0.5 + 0.33 * how.count("\n")
    ax.text(11.3, 1.55, "LOG · PATH · ANCESTORS · MERGE 의 입력은 모두\nparents_map = {hash: (부모 hash, …)} 하나\n"
            "→ graph.py 는 Repository 를 import 하지 않는다", fontsize=10.2, va="top", color=GOOD,
            fontweight="bold", linespacing=1.55)
    finish(fig, [ax], "구조 — 누가 무엇을 책임지나",
           "위 칸은 아래 칸을 부르기만 한다  ·  출력 문자열은 cli.py 만, 상태는 repository.py 만, 알고리즘은 아래 다섯 모듈",
           "architecture.png")


if __name__ == "__main__":
    fig_commit_graph()
    fig_log_orders()
    fig_kahn()
    fig_path()
    fig_ancestors()
    fig_index()
    fig_architecture()
