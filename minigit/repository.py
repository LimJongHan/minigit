"""저장소 — 브랜치, HEAD, 현재 사용자, 커밋 저장소, 역색인을 묶는다.

이 계층은 '값' 만 돌려주고 사람이 읽는 문자열은 cli.py 가 만든다.
알고리즘 자체는 graph.py / sorting.py / index.py 에 있고, 여기서는 호출만 한다.

브랜치는 '커밋 hash 를 가리키는 이름표' 일 뿐이다(실제 Git 의 .git/refs/heads/* 와 같다).
HEAD 는 '지금 어느 이름표 위에 서 있는가' — 브랜치 이름을 가리킨다.
"""

from datetime import datetime

from . import graph
from .commit import CommitStore, HashSpaceExhausted
from .index import CommitIndex
from .sorting import ALGORITHMS

DEFAULT_BRANCH = "main"


class MiniGitError(Exception):
    """사용자에게 그대로 보여줄 오류 메시지를 담는다."""


def invalid_args():
    return MiniGitError("Invalid args")


class Repository:
    def __init__(self, clock=None):
        self._clock = clock or datetime.now
        self.initialized = False
        self.user = None
        self.head = None  # 현재 브랜치 이름
        self.branches = {}  # 브랜치 이름 → commit hash (아직 커밋이 없으면 None)
        self.store = CommitStore()
        self.index = CommitIndex()

    # ------------------------------------------------------------------ 상태
    def _require_init(self):
        if not self.initialized:
            raise MiniGitError("Not a repository. Run: INIT <user_name>")

    def head_commit(self):
        """현재 브랜치가 가리키는 커밋 hash (첫 커밋 전이면 None)."""
        return self.branches.get(self.head)

    def get_commit(self, commit_hash):
        commit = self.store.get(commit_hash)
        if commit is None:
            raise MiniGitError(f"Unknown commit: {commit_hash}")
        return commit

    def resolve(self, ref):
        """커밋을 가리키는 인자 → hash. 정확한 hash 가 우선이고, 다음으로 브랜치 이름, `HEAD`.

        커밋은 hash 로 가리키지만, hash 는 시각에 따라 매번 달라지므로
        `PATH main feature` 처럼 이름으로도 쓸 수 있게 했다(실제 Git 과 같은 편의).
        """
        if ref in self.store:
            return ref
        target = self.branches.get(ref)
        if target is None and ref.upper() == "HEAD":
            target = self.head_commit()
        if target is None:
            raise MiniGitError(f"Unknown commit: {ref}")
        return target

    def parents_map(self):
        return {c.hash: c.parents for c in self.store.all()}

    def labels_for(self, commit_hash):
        """그 커밋을 가리키는 브랜치들. 현재 브랜치는 'HEAD -> main' 으로 표시."""
        labels = []
        if self.branches.get(self.head) == commit_hash:
            labels.append(f"HEAD -> {self.head}")
        for name, target in self.branches.items():
            if target == commit_hash and name != self.head:
                labels.append(name)
        return labels

    # ------------------------------------------------------------- 저장소/브랜치
    def init(self, user):
        """저장소 초기화. 이미 초기화돼 있으면 기록은 그대로 두고 사용자만 바꾼다.

        (실제 `git init` 도 기존 저장소에서 다시 실행하면 이력을 지우지 않는다.)
        반환: 새로 초기화했으면 True, 재초기화면 False.
        """
        user = " ".join(user.split())
        if not user:
            raise invalid_args()
        self.user = user
        if self.initialized:
            return False
        self.initialized = True
        self.head = DEFAULT_BRANCH
        self.branches[DEFAULT_BRANCH] = None
        return True

    @staticmethod
    def _check_branch_name(name):
        if not name or name.startswith("-") or any(ch.isspace() for ch in name):
            raise invalid_args()

    def create_branch(self, name):
        """HEAD 커밋을 가리키는 새 브랜치. 이동(SWITCH) 은 하지 않는다."""
        self._require_init()
        self._check_branch_name(name)
        if name in self.branches:
            raise MiniGitError(f"Branch already exists: {name}")
        if self.head_commit() is None:
            raise MiniGitError("No commits yet")
        self.branches[name] = self.head_commit()

    def switch(self, name, orphan=False):
        """HEAD 를 브랜치로 옮긴다.

        orphan=True 면 '부모 없는 새 브랜치' 를 만들어 옮긴다(`git switch --orphan`).
        거기서 커밋하면 새 루트가 생기고, 기존 이력과 연결되지 않은 그래프 조각이 된다
        → PATH 가 `No path` 를 내는 상황을 CLI 에서 직접 만들 수 있다.
        """
        self._require_init()
        self._check_branch_name(name)
        if orphan:
            if name in self.branches:
                raise MiniGitError(f"Branch already exists: {name}")
            self.branches[name] = None
        elif name not in self.branches:
            raise MiniGitError(f"Unknown branch: {name}")
        changed = self.head != name
        self.head = name
        return changed

    # ------------------------------------------------------------------ 커밋
    def commit(self, message, parents=None, timestamp=None):
        """현재 HEAD 를 부모로 하는 새 커밋. 브랜치를 새 커밋으로 전진시키고 색인을 갱신한다.

        timestamp 를 주면 시계 대신 그 시각을 쓴다(COMMIT --date).
        """
        self._require_init()
        message = message.strip()
        if not message:
            raise invalid_args()
        if parents is None:
            head = self.head_commit()
            parents = () if head is None else (head,)
        if timestamp is None:
            timestamp = self._clock()
        try:
            commit = self.store.create(message, self.user, timestamp, parents)
        except HashSpaceExhausted as exc:
            # 그 커밋만 거부하고 REPL 은 계속 — 잡지 않으면 트레이스백과 함께 프로그램이 죽고 메모리 속 이력도 사라진다
            raise MiniGitError(f"Repository full: {exc}") from exc
        self.branches[self.head] = commit.hash
        self.index.add_commit(commit)
        return commit

    def merge(self, branch_name, message=None):
        """대상 브랜치를 현재 브랜치에 병합 — 부모가 2개인 merge 커밋을 만든다.

        반환: 새 merge 커밋, 또는 이미 포함돼 있으면 None ('Already up to date').
        HEAD 가 대상의 조상이어도(fast-forward 가능) 항상 merge 커밋을 만든다
        (`git merge --no-ff` 와 같은 동작).
        """
        self._require_init()
        if branch_name not in self.branches:
            raise MiniGitError(f"Unknown branch: {branch_name}")
        if branch_name == self.head:
            raise MiniGitError(f"Cannot merge a branch into itself: {branch_name}")
        ours, theirs = self.head_commit(), self.branches[branch_name]
        if theirs is None:
            raise MiniGitError(f"Nothing to merge: {branch_name} has no commits")
        if ours is None:
            raise MiniGitError("No commits yet")
        if graph.is_ancestor(self.parents_map(), theirs, ours):
            return None
        message = message or f"Merge branch '{branch_name}' into {self.head}"
        return self.commit(message, parents=(ours, theirs))

    # ------------------------------------------------------------------ 조회
    def log(self, sort_by=None, algorithm="merge"):
        """커밋 목록.

        sort_by=None   : 위상 정렬 — 부모가 항상 자식보다 먼저. 동시에 준비된 커밋은 생성순.
        sort_by="date" : timestamp 오름차순.
        sort_by="author": 작성자 이름(대소문자 무시) 오름차순.

        date/author 정렬은 **위상 순서를 입력으로** 받아 안정 정렬(merge)한다.
        그래서 동률(같은 시각, 같은 작성자) 끼리는 위상 순서가 그대로 유지된다.
        algorithm 을 'quick'/'heap' 으로 바꾸면 불안정 정렬이 동률 순서를 섞는 걸 볼 수 있다.
        """
        self._require_init()
        if algorithm not in ALGORITHMS:
            raise invalid_args()
        seq_of = {c.hash: c.seq for c in self.store.all()}
        order = graph.topological_order(self.parents_map(), priority=seq_of.__getitem__)
        commits = [self.store.get(h) for h in order]
        if sort_by is None:
            return commits
        sort = ALGORITHMS[algorithm]
        if sort_by == "date":
            return sort(commits, key=lambda c: c.timestamp)
        if sort_by == "author":
            return sort(commits, key=lambda c: c.author.casefold())
        raise invalid_args()

    def path(self, start, goal):
        """무방향 최단 경로(사전순 최소). 없으면 None."""
        self._require_init()
        start, goal = self.resolve(start), self.resolve(goal)
        return graph.shortest_path(self.parents_map(), start, goal)

    def ancestors(self, commit_hash):
        self._require_init()
        commit_hash = self.resolve(commit_hash)
        return [self.store.get(h) for h in graph.ancestors(self.parents_map(), commit_hash)]

    def search_keyword(self, keyword):
        self._require_init()
        if not keyword.strip():
            raise invalid_args()
        return [self.store.get(h) for h in self.index.search_keyword(keyword)]

    def search_author(self, name):
        self._require_init()
        if not name.strip():
            raise invalid_args()
        return [self.store.get(h) for h in self.index.search_author(name)]

