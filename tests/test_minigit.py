"""Mini Git 테스트 — `python -m unittest discover -s tests -v`

테스트 코드도 `sorted()` / `.sort()` 를 쓰지 않는다. 정렬 결과는
'이웃끼리 순서가 맞는가' + '원소 개수가 그대로인가' 로 확인한다.
"""

import ast
import os
import sys
import random
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from minigit import MiniGitCLI, Repository
from minigit import commit as commit_module
from minigit import graph
from minigit import sorting
from minigit.commit import CommitStore
from minigit.diff import diff_lines
from minigit.index import CommitIndex, tokenize
from minigit.sorting import ALGORITHMS, MinHeap

ROOT = Path(__file__).resolve().parent.parent


class FakeClock:
    """호출할 때마다 1분씩 흐르는 시계 — 출력·정렬을 결정적으로 만든다."""

    def __init__(self, start=datetime(2025, 3, 10, 9, 0, 0), step=timedelta(minutes=1)):
        self.now, self.step = start, step

    def __call__(self):
        current = self.now
        self.now += self.step
        return current


def counts(values):
    table = {}
    for v in values:
        table[v] = table.get(v, 0) + 1
    return table


def make_cli():
    return MiniGitCLI(Repository(clock=FakeClock()))


def run(cli, *lines):
    return [cli.execute(line)[0] for line in lines]


def hash_of(output):
    """'[main abc1234] msg' → 'abc1234'"""
    return output.split("]")[0].split()[-1]


# ====================================================================== 정렬
class SortingTests(unittest.TestCase):
    def assert_sorted(self, original, result, key=lambda x: x, reverse=False):
        self.assertEqual(counts(original), counts(result))
        for a, b in zip(result, result[1:]):
            if reverse:
                self.assertGreaterEqual(key(a), key(b))
            else:
                self.assertLessEqual(key(a), key(b))

    def test_all_algorithms_sort_random_inputs(self):
        rng = random.Random(42)
        for name, algo in ALGORITHMS.items():
            for n in (0, 1, 2, 3, 10, 101):
                data = [rng.randint(-20, 20) for _ in range(n)]
                with self.subTest(algo=name, n=n):
                    self.assert_sorted(data, algo(data))
                    self.assert_sorted(data, algo(data, reverse=True), reverse=True)

    def test_does_not_mutate_input(self):
        for name, algo in ALGORITHMS.items():
            data = [3, 1, 2]
            algo(data)
            self.assertEqual(data, [3, 1, 2], name)

    def test_custom_key(self):
        words = ["pear", "fig", "banana", "kiwi"]
        for name, algo in ALGORITHMS.items():
            with self.subTest(algo=name):
                self.assert_sorted(words, algo(words, key=len), key=len)

    def test_merge_and_insertion_are_stable(self):
        # (키, 원래 위치) — 같은 키끼리 원래 위치가 오름차순이면 안정
        rng = random.Random(7)
        data = [(rng.randint(0, 3), i) for i in range(200)]
        for name in ("merge", "insertion"):
            for reverse in (False, True):
                result = ALGORITHMS[name](data, key=lambda p: p[0], reverse=reverse)
                for a, b in zip(result, result[1:]):
                    if a[0] == b[0]:
                        self.assertLess(a[1], b[1], f"{name} reverse={reverse}")

    def test_quick_sort_is_not_stable(self):
        """불안정성은 '보장 안 됨' 이지 '항상 섞임' 은 아니다 — 섞이는 입력이 하나라도 있으면 된다."""
        data = [(i % 3, i) for i in range(60)]
        result = ALGORITHMS["quick"](data, key=lambda p: p[0])
        broken = any(a[0] == b[0] and a[1] > b[1] for a, b in zip(result, result[1:]))
        self.assertTrue(broken)

    def test_quick_sort_handles_sorted_and_equal_inputs(self):
        # 정렬된 입력·같은 값 대량에서도 재귀/스택이 터지지 않아야 한다
        self.assert_sorted(list(range(5000)), ALGORITHMS["quick"](list(range(5000))))
        self.assert_sorted([1] * 5000, ALGORITHMS["quick"]([1] * 5000))

    def test_quick_sort_stack_stays_logarithmic(self):
        """피벗을 일부러 매번 최악(구간 끝)으로 골라도 미뤄둔 구간 수가 log n 수준이어야 한다."""
        class WorstPivot:
            def randint(self, lo, hi):
                return hi

        peak = [0]
        original_partition = sorting._partition3

        def spy(arr, lo, hi, reverse, rng):
            frame = sys._getframe(1)
            peak[0] = max(peak[0], len(frame.f_locals["stack"]))
            return original_partition(arr, lo, hi, reverse, rng)

        sorting._partition3 = spy
        try:
            result = sorting.quick_sort(list(range(2000)), rng=WorstPivot())
        finally:
            sorting._partition3 = original_partition
        self.assertEqual(result, list(range(2000)))
        self.assertLessEqual(peak[0], 12)  # log2(2000) ≈ 11

    def test_min_heap(self):
        heap = MinHeap()
        for v in [5, 3, 8, 1, 9, 2]:
            heap.push(v)
        self.assertEqual([heap.pop() for _ in range(6)], [1, 2, 3, 5, 8, 9])
        with self.assertRaises(IndexError):
            heap.pop()

    def test_no_standard_sort_api_in_source(self):
        """직접 구현 원칙: sorted() / .sort() 금지 — AST 로 실제 '호출' 만 찾는다(주석·docstring 은 무시)."""
        files = [ROOT / "main.py", ROOT / "bench_sort.py"]
        for folder in ("minigit", "tests", "demo", "docs"):
            files += list((ROOT / folder).glob("*.py"))
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                self.assertFalse(isinstance(func, ast.Name) and func.id == "sorted",
                                 f"sorted() in {path.name}:{node.lineno}")
                self.assertFalse(isinstance(func, ast.Attribute) and func.attr == "sort",
                                 f".sort() in {path.name}:{node.lineno}")


# ====================================================================== 그래프
def random_dag(rng, n, merge_rate=0.3):
    """생성 순서대로 노드를 만들며 부모를 '이전 노드' 중에서만 고른다 → 반드시 DAG."""
    parents_map = {}
    names = []
    for i in range(n):
        name = f"{rng.randrange(16 ** 4):04x}{i:03d}"[-7:]
        if i == 0 or rng.random() < 0.05:
            parents = ()
        elif rng.random() < merge_rate and i >= 2:
            a, b = rng.sample(names, 2)
            parents = (a, b)
        else:
            parents = (rng.choice(names),)
        parents_map[name] = parents
        names.append(name)
    return parents_map


def brute_force_best_path(parents_map, start, goal):
    """모든 단순 경로를 DFS 로 나열 → 가장 짧은 것 중 문자열 최소. 작은 그래프 검증용."""
    adjacency = graph.undirected_adjacency(parents_map)
    best = None

    def dfs(node, path, seen):
        nonlocal best
        if best is not None and len(path) > len(best):
            return
        if node == goal:
            if best is None or len(path) < len(best) or "->".join(path) < "->".join(best):
                best = list(path)
            return
        for nb in adjacency[node]:
            if nb not in seen:
                seen.add(nb)
                path.append(nb)
                dfs(nb, path, seen)
                path.pop()
                seen.remove(nb)

    dfs(start, [start], {start})
    return best


class GraphTests(unittest.TestCase):
    DIAMOND = {  # a ← b, a ← c, (c, b) ← d   : d 는 merge 커밋
        "aaaaaaa": (),
        "ccccccc": ("aaaaaaa",),
        "bbbbbbb": ("aaaaaaa",),
        "ddddddd": ("ccccccc", "bbbbbbb"),
    }

    def test_topological_order_parents_first(self):
        rng = random.Random(1)
        for _ in range(30):
            pm = random_dag(rng, 40)
            order = graph.topological_order(pm)
            position = {node: i for i, node in enumerate(order)}
            self.assertEqual(len(order), len(pm))
            for node, parents in pm.items():
                for p in parents:
                    self.assertLess(position[p], position[node])

    def test_topological_order_uses_priority_for_ties(self):
        order = graph.topological_order(self.DIAMOND)
        self.assertEqual(order, ["aaaaaaa", "bbbbbbb", "ccccccc", "ddddddd"])
        prio = {"aaaaaaa": 0, "ccccccc": 1, "bbbbbbb": 2, "ddddddd": 3}
        order = graph.topological_order(self.DIAMOND, priority=prio.__getitem__)
        self.assertEqual(order, ["aaaaaaa", "ccccccc", "bbbbbbb", "ddddddd"])

    def test_cycle_is_detected(self):
        with self.assertRaises(ValueError):
            graph.topological_order({"x": ("y",), "y": ("x",)})

    def test_shortest_path_lexicographic_tie_break(self):
        # d → a 최단 경로는 d-b-a, d-c-a 두 개 (둘 다 2칸). 사전순으로 b 쪽.
        self.assertEqual(graph.shortest_path(self.DIAMOND, "ddddddd", "aaaaaaa"),
                         ["ddddddd", "bbbbbbb", "aaaaaaa"])
        # 형제끼리는 부모를 거치거나 merge 자식을 거치거나 — 둘 다 2칸, a 가 d 보다 작다
        self.assertEqual(graph.shortest_path(self.DIAMOND, "bbbbbbb", "ccccccc"),
                         ["bbbbbbb", "aaaaaaa", "ccccccc"])

    def test_shortest_path_same_node_and_no_path(self):
        self.assertEqual(graph.shortest_path(self.DIAMOND, "aaaaaaa", "aaaaaaa"), ["aaaaaaa"])
        islands = {"aaaaaaa": (), "bbbbbbb": ()}
        self.assertIsNone(graph.shortest_path(islands, "aaaaaaa", "bbbbbbb"))

    def test_shortest_path_matches_brute_force(self):
        rng = random.Random(3)
        for _ in range(60):
            pm = random_dag(rng, 9, merge_rate=0.5)
            nodes = list(pm)
            start, goal = rng.choice(nodes), rng.choice(nodes)
            self.assertEqual(graph.shortest_path(pm, start, goal),
                             brute_force_best_path(pm, start, goal), (pm, start, goal))

    def test_ancestors_complete_without_duplicates(self):
        result = graph.ancestors(self.DIAMOND, "ddddddd")
        self.assertEqual(result, ["ccccccc", "bbbbbbb", "aaaaaaa"])  # 가까운 세대부터
        self.assertEqual(graph.ancestors(self.DIAMOND, "aaaaaaa"), [])

    def test_ancestors_match_reachability(self):
        rng = random.Random(5)
        pm = random_dag(rng, 80, merge_rate=0.4)
        for node in pm:
            expected = set()
            stack = list(pm[node])
            while stack:
                p = stack.pop()
                if p not in expected:
                    expected.add(p)
                    stack.extend(pm[p])
            got = graph.ancestors(pm, node)
            self.assertEqual(len(got), len(set(got)))
            self.assertEqual(set(got), expected)


# ====================================================================== 커밋/해시
class CommitStoreTests(unittest.TestCase):
    def test_hash_unique_even_with_forced_collisions(self):
        """해시를 1자리(16가지)로 줄이면 충돌이 확실히 난다 — 그래도 16개는 모두 달라야 한다."""
        original = commit_module.HASH_LENGTH
        commit_module.HASH_LENGTH = 1
        try:
            store = CommitStore()
            ts = datetime(2024, 1, 1)
            hashes = [store.create("same", "same", ts).hash for _ in range(16)]
            self.assertEqual(len(set(hashes)), 16)
            with self.assertRaises(RuntimeError):  # 17번째는 무한 루프 대신 즉시 실패
                store.create("same", "same", ts)
            # CLI 에서는 트레이스백으로 죽지 않고 메시지 → 그 커밋만 거부, 나머지 명령은 계속
            cli = make_cli()
            run(cli, "init A", *[f"commit c{i}" for i in range(16)])
            output, keep_running = cli.execute("commit one-too-many")
            self.assertEqual(output, "Repository full: hash space exhausted: 16 commits")
            self.assertTrue(keep_running)
            self.assertEqual(cli.execute("log")[0].count("commit "), 16)
        finally:
            commit_module.HASH_LENGTH = original

    def test_unknown_parent_rejected(self):
        with self.assertRaises(ValueError):
            CommitStore().create("m", "a", datetime(2024, 1, 1), parents=("nope",))

    def test_commit_fields(self):
        c = CommitStore().create("msg", "Ari", datetime(2024, 1, 1))
        for field in ("hash", "message", "author", "timestamp", "parents"):
            self.assertTrue(hasattr(c, field))
        self.assertEqual(len(c.hash), commit_module.HASH_LENGTH)


# ====================================================================== 역색인
class IndexTests(unittest.TestCase):
    def setUp(self):
        self.store = CommitStore()
        self.index = CommitIndex()
        ts = datetime(2024, 1, 1)
        for msg, author in [("Add signup feature", "Ari"),
                            ("Fix SIGNUP, signout bug", "Ben"),
                            ("signup signup signup", "ari"),
                            ("Add cart", "Ben")]:
            c = self.store.create(msg, author, ts)
            self.index.add_commit(c)
        self.hashes = [c.hash for c in self.store.all()]

    def test_tokenize_lowercases_and_strips_edge_punctuation(self):
        self.assertEqual(tokenize('Fix "SIGNUP," bug!'), ["fix", "signup", "bug"])
        self.assertEqual(tokenize("e-mail v1.2"), ["e-mail", "v1.2"])

    def test_keyword_search_case_insensitive_no_duplicates(self):
        h = self.hashes
        self.assertEqual(self.index.search_keyword("SIGNUP"), [h[0], h[1], h[2]])
        self.assertEqual(self.index.search_keyword("cart"), [h[3]])
        self.assertEqual(self.index.search_keyword("nothing"), [])

    def test_multi_word_query_is_and(self):
        self.assertEqual(self.index.search_keyword("add signup"), [self.hashes[0]])

    def test_author_search_normalized(self):
        h = self.hashes
        self.assertEqual(self.index.search_author("ARI"), [h[0], h[2]])
        self.assertEqual(self.index.search_author("ben"), [h[1], h[3]])

    def test_index_has_both_kinds(self):
        self.assertIn("signup", self.index.keywords.keys())
        self.assertIn("ari", self.index.authors.keys())


# ====================================================================== CLI
class CLITests(unittest.TestCase):
    def test_example_scenario(self):
        cli = make_cli()
        out = run(cli, 'init "Ari"', 'commit "Set up project"', "branch feature",
                  "switch feature", 'commit "Add signup feature"', "switch main",
                  'commit "Add cart feature"')
        self.assertIn("Initialized repository.", out[0])
        self.assertIn("Current user: Ari", out[0])
        a, d, g = hash_of(out[1]), hash_of(out[4]), hash_of(out[6])
        self.assertTrue(out[4].startswith("[feature "))
        self.assertEqual(out[2], "Created branch: feature")
        self.assertEqual(out[3], "Switched to branch: feature")

        log = cli.execute("log")[0]
        self.assertLess(log.index(a), log.index(d))
        self.assertLess(log.index(a), log.index(g))
        self.assertIn("(Ari, 2025-03-10 09:00:00)", log)

        self.assertEqual(cli.execute(f"path {a} {g}")[0], f"Path: {a} -> {g} (1 edge)")
        search = cli.execute('search "signup"')[0]
        self.assertTrue(search.startswith("Found 1 commit:"))
        self.assertIn(f"- {d}: Add signup feature", search)

    def test_commands_case_insensitive(self):
        cli = make_cli()
        out = run(cli, "INIT ben", "Commit hello", "LoG")
        self.assertIn("Initialized", out[0])
        self.assertIn("hello", out[2])
        self.assertEqual(cli.execute("  # 시연 설명 줄")[0], "")  # 주석 줄은 무시

    def test_unquoted_multiword_args_are_joined(self):
        cli = make_cli()
        out = run(cli, "init Ari Kim", "commit Add signup feature")
        self.assertIn("Current user: Ari Kim", out[0])
        self.assertTrue(out[1].endswith("] Add signup feature"))

    def test_standard_errors(self):
        cli = make_cli()
        self.assertIn("Not a repository", cli.execute("commit x")[0])
        run(cli, "init A")
        self.assertEqual(cli.execute("branch early")[0], "No commits yet")
        run(cli, "commit one")
        self.assertEqual(cli.execute("commit")[0], "Invalid args")
        self.assertEqual(cli.execute("init")[0], "Invalid args")
        self.assertEqual(cli.execute("switch nope")[0], "Unknown branch: nope")
        self.assertEqual(cli.execute("ancestors zzz")[0], "Unknown commit: zzz")
        self.assertEqual(cli.execute("path zzz main")[0], "Unknown commit: zzz")
        self.assertEqual(cli.execute("path main")[0], "Invalid args")
        self.assertEqual(cli.execute("log --sort-by=size")[0], "Invalid args")
        self.assertEqual(cli.execute("search --author")[0], "Invalid args")
        self.assertEqual(cli.execute("branch main")[0], "Branch already exists: main")
        self.assertEqual(cli.execute("frob")[0], "Unknown command: frob")
        self.assertEqual(cli.execute('commit "open')[0], "Invalid args (unclosed quote)")

    def test_exit_and_quit(self):
        cli = make_cli()
        self.assertFalse(cli.execute("exit")[1])
        self.assertFalse(cli.execute("QUIT")[1])
        self.assertTrue(cli.execute("")[1])
        # main.repl + --fixed-clock: 같은 스크립트 → 같은 hash (시연 스크립트에 hash 를 적을 수 있다)
        import io
        import main
        script = "# 설명\ninit A\ncommit one\nexit\n"
        runs = []
        for _ in range(2):
            out = io.StringIO()
            main.repl(stdin=io.StringIO(script), stdout=out, clock=main.StepClock())
            runs.append(out.getvalue())
        self.assertEqual(runs[0], runs[1])
        self.assertIn("# 설명\n", runs[0])
        self.assertNotIn("mini-git> # 설명", runs[0])

    def test_log_sort_by_author_and_date(self):
        repo = Repository(clock=FakeClock())
        cli = MiniGitCLI(repo)
        run(cli, "init Zed", "commit z1", "init Amy", "commit a1", "init Zed", "commit z2")
        by_author = [c.message for c in repo.log(sort_by="author")]
        self.assertEqual(by_author, ["a1", "z1", "z2"])  # Zed 끼리는 위상(생성) 순서 유지 = 안정
        by_date = [c.message for c in repo.log(sort_by="date")]
        self.assertEqual(by_date, ["z1", "a1", "z2"])
        self.assertIn("commit", cli.execute("log --sort-by=DATE")[0])
        # 시계가 틀린 커밋(자식이 부모보다 과거): LOG 는 관계(부모 먼저), date 정렬은 시각
        run(cli, 'commit --date="2000-01-01 00:00:00" skewed')
        self.assertEqual(repo.log()[-1].message, "skewed")
        self.assertEqual(repo.log(sort_by="date")[0].message, "skewed")
        self.assertEqual(cli.execute("commit --date=yesterday x")[0], "Invalid args")

    def test_reinit_keeps_history(self):
        cli = make_cli()
        run(cli, "init A", "commit one")
        out = cli.execute("init B")[0]
        self.assertIn("Reinitialized", out)
        self.assertIn("one", cli.execute("log")[0])

    def test_ancestors_and_refs(self):
        cli = make_cli()
        out = run(cli, "init A", "commit c1", "commit c2", "commit c3")
        c1, c2 = hash_of(out[1]), hash_of(out[2])
        result = cli.execute("ancestors HEAD")[0]
        self.assertTrue(result.startswith("Ancestors of HEAD (2 commits):"))
        self.assertLess(result.index(c2), result.index(c1))
        self.assertIn("(0 commits)", cli.execute(f"ancestors {c1}")[0])
        # 사용자 입력은 템플릿이 아니다 — 중괄호가 든 브랜치 이름도 머리말에 그대로 나와야 한다
        run(cli, "branch {count}", "branch a{b}")
        self.assertTrue(cli.execute("ancestors {count}")[0].startswith("Ancestors of {count} (2 commits):"))
        self.assertTrue(cli.execute("ancestors a{b}")[0].startswith("Ancestors of a{b} (2 commits):"))

    def test_orphan_branch_gives_no_path(self):
        cli = make_cli()
        run(cli, "init A", "commit base", "switch --orphan docs", "commit docs-root")
        self.assertEqual(cli.execute("path docs main")[0], "No path")

    def test_merge_creates_two_parent_commit(self):
        repo = Repository(clock=FakeClock())
        cli = MiniGitCLI(repo)
        run(cli, "init A", "commit base", "branch f", "switch f", "commit on-f",
            "switch main", "commit on-main")
        ours, theirs = repo.branches["main"], repo.branches["f"]
        out = cli.execute("merge f")[0]
        merge = repo.store.get(repo.branches["main"])
        self.assertEqual(merge.parents, (ours, theirs))
        self.assertIn("Merge:", out)
        self.assertEqual(cli.execute("merge f")[0], "Already up to date.")
        self.assertEqual(cli.execute("merge main")[0], "Cannot merge a branch into itself: main")
        ancestors = cli.execute("ancestors HEAD")[0]
        self.assertIn("(3 commits)", ancestors)  # base 는 두 갈래로 닿지만 한 번만

    def test_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            f1, f2 = os.path.join(tmp, "a.txt"), os.path.join(tmp, "b.txt")
            Path(f1).write_text("a\nb\nc\n", encoding="utf-8")
            Path(f2).write_text("a\nx\nc\nd\n", encoding="utf-8")
            out = make_cli().execute(f'diff "{f1}" "{f2}"')[0]
            self.assertIn("  a", out)
            self.assertIn("- b", out)
            self.assertIn("+ x", out)
            self.assertIn("+ d", out)
            self.assertIn("(2 added, 1 removed, 2 unchanged)", out)
            missing = make_cli().execute(f'diff "{f1}" "{tmp}/none.txt"')[0]
            self.assertTrue(missing.startswith("File not found"))

    def test_diff_lines_lcs(self):
        self.assertEqual(diff_lines(["a", "b"], ["a", "b"]), [(" ", "a"), (" ", "b")])
        self.assertEqual(diff_lines([], ["x"]), [("+", "x")])
        self.assertEqual(diff_lines(["x"], []), [("-", "x")])


if __name__ == "__main__":
    unittest.main()
