"""features 시연을 그림 한 장으로 — demo/features_graph.png

    python3 demo/draw_features.py

그래프 구조는 features.txt 를 실제로 재생해서(--fixed-clock 과 같은 시계) 얻고,
출력 순서(LOG · 정렬 · PATH · ANCESTORS · SEARCH)는 features.out 에서 읽는다.
그래서 그림은 시연 결과와 어긋날 수 없다 — 스크립트나 코드가 바뀌면 다시 돌리면 된다.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from scenario import ROOT  # noqa: E402

import main  # noqa: E402
from minigit import MiniGitCLI, Repository  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "features.txt")
OUTPUT = os.path.join(HERE, "features.out")
PNG = os.path.join(HERE, "features_graph.png")

font_manager.fontManager.addfont("/System/Library/Fonts/AppleSDGothicNeo.ttc")
plt.rcParams["font.family"] = "Apple SD Gothic Neo"
MONO = "Menlo"

# ── 색 ────────────────────────────────────────────────────────────────
INK, MUTED, FAINT, LINE = "#1f2328", "#57606a", "#d0d7de", "#8c959f"
AUTHOR = {"Ari": ("#2f6fb3", "#dbe9f7"), "Ben": ("#c4610f", "#fde7d2")}
GOOD, BAD, WARN = "#1a7f37", "#cf222e", "#bf3989"


# ── 1. 시연 재생 → 그래프 구조 ─────────────────────────────────────────
def replay():
    repo = Repository(clock=main.StepClock())
    cli = MiniGitCLI(repo)
    created_by = {}
    pending = []
    with open(SCRIPT, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.lower() in ("exit", "quit"):
                continue
            before = set(repo.store._commits)
            result, _ = cli.execute(line)
            if result.startswith(("Not a repository", "Invalid", "Unknown")):
                continue  # 실패한 명령은 그래프를 안 바꾼다
            if line.startswith("commit --date="):
                line = 'commit --date="… 08:00:00" "…"'
            pending.append(line)
            new = set(repo.store._commits) - before
            for h in new:
                created_by[h] = [p for p in pending if not p.lower().startswith(("log", "path", "ancestors", "search", "branch"))]
                pending = []
    return repo, created_by


def parse_output():
    """features.out → {명령: [출력 줄...]} (같은 명령이 여러 번이면 리스트에 순서대로)."""
    blocks, current = {}, None
    with open(OUTPUT, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line.startswith("mini-git> "):
                current = line[len("mini-git> "):]
                blocks.setdefault(current, []).append([])
            elif line.startswith("#") or not line.strip():
                continue
            elif current is not None:
                blocks[current][-1].append(line)
    return blocks


def hashes_in(lines, kind):
    if kind == "log":
        return [ln.split()[1] for ln in lines if ln.startswith("commit ")]
    if kind == "list":
        return [ln[2:].split(":")[0] for ln in lines if ln.startswith("- ")]
    if kind == "path":
        text = lines[0]
        return [] if text == "No path" else text[len("Path: "):].split(" (")[0].split(" -> ")


repo, created_by = replay()
out = parse_output()
commits = {c.hash: c for c in repo.store.all()}
order = [c.hash for c in repo.store.all()]
ALIAS = dict(zip(order, ["A", "L", "P", "M1", "F", "M2", "S", "D"]))
BY_ALIAS = {v: k for k, v in ALIAS.items()}
LANE = {"A": "main", "L": "feature", "P": "main", "M1": "main", "F": "feature",
        "M2": "main", "S": "main", "D": "docs"}
LANE_Y = {"main": 2.0, "feature": 0.75, "docs": -1.25}
POS = {h: (i * 2.25, LANE_Y[LANE[ALIAS[h]]]) for i, h in enumerate(order)}
EDGES = [(h, p) for h in order for p in commits[h].parents]  # 자식 → 부모


def short_msg(h):
    m = commits[h].message
    return {"Merge branch 'feature' into main": "merge feature → main",
            "Commit from a skewed clock": "시계가 틀린 커밋"}.get(m, m)


def edge_line(ax, child, parent, color=LINE, lw=1.6, style="-", alpha=1.0, z=1, scale=1.0):
    (x1, y1), (x2, y2) = POS[child], POS[parent]
    half = 0.85 * scale
    start, end = (x1 - half, y1), (x2 + half, y2)
    rad = 0.0 if y1 == y2 else (0.18 if y1 > y2 else -0.18)
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14 * scale,
                                 color=color, lw=lw, linestyle=style, alpha=alpha, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))


def node(ax, h, scale=1.0, dim=False, ring=None, badge=None, detail=True):
    x, y = POS[h]
    c = commits[h]
    edge, fill = AUTHOR[c.author]
    if dim:
        edge, fill = FAINT, "#f6f8fa"
    w, hgt = 1.7 * scale, (0.95 if detail else 0.62) * scale
    merge = len(c.parents) > 1
    ax.add_patch(FancyBboxPatch((x - w / 2, y - hgt / 2), w, hgt, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fill, ec=ring or edge, lw=(3.2 if ring else (2.2 if merge else 1.4)), zorder=3))
    tc = MUTED if dim else INK
    if detail:
        ax.text(x - w / 2 + 0.1, y + 0.22, ALIAS[h], fontsize=16, fontweight="bold", color=edge if not dim else MUTED,
                va="center", zorder=4)
        ax.text(x + w / 2 - 0.1, y + 0.22, h, fontsize=8.5, family=MONO, color=tc, ha="right", va="center", zorder=4)
        ax.text(x, y - 0.06, short_msg(h), fontsize=8.5, color=tc, ha="center", va="center", zorder=4)
        t = c.timestamp.strftime("%H:%M")
        skew = any(commits[p].timestamp > c.timestamp for p in c.parents)
        ax.text(x, y - 0.3, f"{c.author} · {t}" + ("  ← 부모보다 과거!" if skew else ""), fontsize=8,
                color=BAD if skew else MUTED, ha="center", va="center", zorder=4, fontweight="bold" if skew else None)
    else:
        ax.text(x, y + 0.08, ALIAS[h], fontsize=13 * scale / 0.75, fontweight="bold",
                color=edge if not dim else MUTED, ha="center", va="center", zorder=4)
        ax.text(x, y - 0.17, h[:4], fontsize=7, family=MONO, color=MUTED, ha="center", va="center", zorder=4)
    if badge is not None:
        bx, by = x + w / 2 - 0.05, y + hgt / 2 + 0.02
        ax.add_patch(plt.Circle((bx, by), 0.17 * max(scale, 0.8), color=badge[1], zorder=5))
        ax.text(bx, by, str(badge[0]), color="white", fontsize=9, fontweight="bold", ha="center", va="center", zorder=6)


def tag(ax, x, y, text, color, mono=False):
    ax.text(x, y, text, fontsize=9, color="white", ha="center", va="center", zorder=6,
            family=MONO if mono else None, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.3", fc=color, ec="none"))


def frame(ax, xlim, ylim):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")


# ── 2. 그림 ───────────────────────────────────────────────────────────
W = 19.0
_half = (W - 0.9) / 2
H_TOTAL = (1.25 + (W - 0.6) * 5.4 / 19.9 + 0.25 + (W - 0.6) * 7.55 / 34.7 + 0.25
           + _half * 4.4 / 15.8 + 0.25 + _half * 6.25 / 18.0 + 0.15)
fig = plt.figure(figsize=(W, H_TOTAL), dpi=110, facecolor="white")
H = fig.get_figheight()
cursor = [H - 1.25]          # 위에서부터 inch 단위로 내려가며 axes 를 놓는다


def place(height, left=0.3, width=W - 0.6, advance=True):
    """(위에서부터) height inch 짜리 axes. data 비율에 맞춘 높이를 넘겨 빈 공간을 없앤다."""
    bottom = cursor[0] - height
    axp = fig.add_axes([left / W, bottom / H, width / W, height / H])
    if advance:
        cursor[0] = bottom - 0.25
    return axp


fig.text(0.3 / W, (H - 0.45) / H, "features — 시연이 만드는 커밋 그래프와 출력 흐름",
         fontsize=22, fontweight="bold", va="center")
fig.text(0.3 / W, (H - 0.9) / H, "python3 main.py --fixed-clock < demo/features.txt   ·   화살표 = 자식 → 부모   ·   "
         "파랑 = Ari, 주황 = Ben   ·   굵은 테두리 = merge 커밋   ·   ①~⑧ = 만들어진 순서(생성 순번 seq)",
         fontsize=11.5, color=MUTED, va="center")

# ── 2-1. 메인 그래프 ──────────────────────────────────────────────────
ax = place((W - 0.6) * 5.4 / 19.9)
for lane, y in LANE_Y.items():
    ax.axhline(y, color="#eaeef2", lw=18, zorder=0, solid_capstyle="butt")
    ax.text(-1.55, y, {"main": "main", "feature": "feature", "docs": "docs\n(orphan)"}[lane],
            fontsize=12, fontweight="bold", color=MUTED, ha="right", va="center")
ax.plot([-1.4, 17.2], [-0.5, -0.5], color=LINE, lw=1, ls=(0, (4, 4)), zorder=0)
ax.text(13.6, -1.25, "docs 는 부모 없는 새 루트 — 점선 위쪽과 이어지는 선이 없다\n→ path docs main = No path  →",
        fontsize=10, color=BAD, ha="right", va="center", linespacing=1.5)
for child, parent in EDGES:
    edge_line(ax, child, parent)
seq_colors = ["#6e7781"] * 8
for i, h in enumerate(order):
    node(ax, h, badge=(i + 1, seq_colors[i]))
    cmds = created_by.get(h, [])
    if cmds:
        x, y = POS[h]
        ax.text(x, y - 0.62, "\n".join(cmds[-3:]), fontsize=7.6, family=MONO, color=MUTED, ha="center", va="top")
mx = (POS[BY_ALIAS["M1"]][0] + POS[BY_ALIAS["F"]][0]) / 2
ax.plot([mx, mx], [-0.45, 2.65], color=AUTHOR["Ben"][0], lw=1.2, ls=(0, (2, 3)), zorder=0)
ax.text(mx, 2.75, 'init "Ben" — 여기부터 작성자 Ben', fontsize=9.5, color=AUTHOR["Ben"][0], ha="center", va="bottom")
x, y = POS[BY_ALIAS["S"]]
tag(ax, x, y + 0.82, "HEAD → main", INK)
x, y = POS[BY_ALIAS["F"]]
tag(ax, x, y + 0.72, "feature", MUTED)
x, y = POS[BY_ALIAS["D"]]
tag(ax, x, y + 0.72, "docs", MUTED)
x, y = POS[BY_ALIAS["M1"]]
ax.text(x, y + 0.62, "부모 2개 (P, L)", fontsize=8.5, color=MUTED, ha="center")
x, y = POS[BY_ALIAS["M2"]]
ax.text(x, y + 0.62, "부모 2개 (M1, F)", fontsize=8.5, color=MUTED, ha="center")
frame(ax, (-2.6, 17.3), (-2.35, 3.05))

# ── 2-2. 출력 순서 띠 ─────────────────────────────────────────────────
ax = place((W - 0.6) * 7.55 / 34.7)
rows = [
    ("LOG", hashes_in(out["log"][1], "log"),
     "위상 정렬 — 부모가 항상 먼저. S 는 08:00 인데도 부모 M2 뒤 (시각이 아니라 관계)"),
    ("LOG --sort-by=date", hashes_in(out["log --sort-by=date"][0], "log"),
     "시각순 — 08:00 의 S 가 맨 앞으로. 부모보다 먼저 나오는 자식이 생긴다"),
    ("LOG --sort-by=author", hashes_in(out["log --sort-by=author"][0], "log"),
     "작성자순 (안정 병합 정렬) — Ari 묶음 → Ben 묶음, 묶음 안은 위상 순서 그대로"),
    ("ANCESTORS HEAD", hashes_in(out["ancestors HEAD"][0], "list"),
     "S 의 조상 6개, 가까운 세대부터(BFS). L 은 M1·F 두 갈래로 닿지만 한 번만"),
    ("SEARCH signup", hashes_in(out["search signup"][0], "list"),
     "역색인 'signup' → [L, F]. F 의 'SIGNUP,' 도 소문자·쉼표 제거로 같은 토큰"),
    ("SEARCH --author=ben", hashes_in(out["search --author=ben"][0], "list"),
     "역색인 'ben' → 생성순 posting 그대로"),
]
for r, (title, seq, note) in enumerate(rows):
    y = -r * 1.25
    ax.text(-0.3, y, title, fontsize=12, fontweight="bold", family=MONO, color=INK, ha="right", va="center")
    for i, h in enumerate(seq):
        cx = 0.6 + i * 1.55
        edge, fill = AUTHOR[commits[h].author]
        skew = ALIAS[h] == "S"
        ax.add_patch(FancyBboxPatch((cx - 0.6, y - 0.36), 1.2, 0.72, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=fill, ec=BAD if skew else edge, lw=2.4 if skew else 1.3, zorder=3))
        ax.text(cx, y + 0.1, ALIAS[h], fontsize=13, fontweight="bold", color=edge, ha="center", va="center", zorder=4)
        ax.text(cx, y - 0.19, h, fontsize=7, family=MONO, color=MUTED, ha="center", va="center", zorder=4)
        if i:
            ax.annotate("", (cx - 0.62, y), (cx - 0.93, y), arrowprops=dict(arrowstyle="-|>", color=LINE, lw=1.2))
        if title == "LOG --sort-by=author" and i and commits[seq[i - 1]].author != commits[h].author:
            ax.plot([cx - 0.775] * 2, [y - 0.5, y + 0.5], color=INK, lw=2)
    ax.text(0.6 + 8 * 1.55 - 0.3, y, note, fontsize=10.5, color=MUTED, va="center")
frame(ax, (-5.2, 29.5), (-6.8, 0.75))

# ── 2-3. 작은 그래프 4개 ──────────────────────────────────────────────
MAIN_ONLY = [h for h in order if ALIAS[h] != "D"]


def mini(axm, title, subtitle, path=None, rejected=(), numbered=None, isolated=False, start=None):
    hl_edges = set()
    if path:
        hl_edges = {frozenset(e) for e in zip(path, path[1:])}
    for child, parent in EDGES:
        key = frozenset((child, parent))
        if key in hl_edges:
            edge_line(axm, child, parent, color=GOOD, lw=4, z=2, scale=0.75)
        elif any(key in r for r in rejected):
            edge_line(axm, child, parent, color=BAD, lw=2.4, style=(0, (3, 2)), z=2, scale=0.75)
        else:
            edge_line(axm, child, parent, color=FAINT, lw=1.2, scale=0.75)
    shown = order if isolated else MAIN_ONLY
    for h in shown:
        on = (path and h in path) or (numbered and h in numbered) or (isolated and ALIAS[h] in ("D",))
        badge = None
        if numbered and h in numbered:
            badge = (numbered.index(h) + 1, GOOD)
        if path and h in path:
            badge = (path.index(h) + 1, GOOD)
        ring = BAD if (isolated and ALIAS[h] == "D") else (INK if h == start else None)
        node(axm, h, scale=0.75, dim=not on and not isolated and h != start, ring=ring, badge=badge, detail=False)
        if h == start:
            x, y = POS[h]
            axm.text(x, y + 0.48, "시작 (HEAD)", fontsize=9, color=INK, ha="center", fontweight="bold")
    axm.text(-1.3, 3.25, title, fontsize=13.5, fontweight="bold", color=INK, va="bottom")
    axm.text(-1.3, 2.95, subtitle, fontsize=9.8, color=MUTED, va="top", linespacing=1.45)
    frame(axm, (-1.4, 16.6), (-1.85, 4.4)) if isolated else frame(axm, (-1.4, 14.4), (0.0, 4.4))


p_fp = hashes_in(out["path 8ff2dea 7333cf5"][0], "path")
half = (W - 0.9) / 2
row_h = half * 4.4 / 15.8
mini(place(row_h, width=half, advance=False), "PATH F → P",
     f"무방향 BFS, 3칸 후보 셋: F-L-A-P · F-L-M1-P · F-M2-M1-P\n"
     f"앞 칸부터 hash 비교 → 1cdd < a16e, 4280 < 70cf → 초록 길 (공통 조상 A 를 거쳐 '올라갔다 내려옴')",
     path=p_fp)
p_pl = hashes_in(out["path 7333cf5 1cdd61f"][0], "path")
M1, P, L = BY_ALIAS["M1"], BY_ALIAS["P"], BY_ALIAS["L"]
mini(place(row_h, left=0.6 + half, width=half), "PATH P → L  (동률)",
     f"2칸짜리가 둘: P-A-L 과 P-M1-L (빨간 점선)\n"
     f"가운데 칸 비교: 4280179 < 70cfbfe → A 쪽이 사전순 최소",
     path=p_pl, rejected=[{frozenset((M1, P)), frozenset((M1, L))}])
anc = hashes_in(out["ancestors HEAD"][0], "list")
mini(place(half * 6.25 / 18.0, width=half, advance=False), "ANCESTORS HEAD (= S)",
     "번호 = 출력 순서 (가까운 세대부터 BFS)\nL 은 M1 경유 · F 경유 두 번 닿지만 방문 집합(seen) 덕에 한 번만 → 6개",
     numbered=anc, start=BY_ALIAS["S"])
mini(place(half * 6.25 / 18.0, left=0.6 + half, width=half), "PATH docs main → No path",
     "docs(D) 는 switch --orphan 으로 만든 부모 없는 새 루트\n간선을 무방향으로 봐도 위쪽 덩어리와 이어지는 선이 하나도 없다",
     isolated=True)

fig.savefig(PNG, dpi=110, facecolor="white")
print(f"saved {os.path.relpath(PNG, ROOT)}")
