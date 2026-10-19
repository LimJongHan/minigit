"""커밋 노드와 커밋 저장소(해시맵).

커밋 그래프의 간선은 **자식 → 부모** 방향으로만 저장한다(`parents`).
커밋은 만들어진 뒤 바뀌지 않고(불변), 부모는 반드시 '이미 존재하는' 커밋이어야 한다.
그래서 새 간선은 항상 '새 노드 → 옛 노드' 로만 생기고, 사이클이 생길 수 없다 → DAG.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

HASH_LENGTH = 7  # 실제 Git 의 짧은 해시 기본 길이. 길이를 고정해 PATH 사전순 비교를 '칸별 비교' 로 바로 읽을 수 있게 한다.


class HashSpaceExhausted(RuntimeError):
    """hash 공간(16^HASH_LENGTH 개)이 꽉 차서 새 hash 를 만들 수 없다.

    RuntimeError 를 통째로 잡지 않고 이것만 골라 잡을 수 있게 따로 둔다
    (Repository 가 사용자용 메시지로 바꾼다 — 이 모듈은 CLI 를 모른다).
    """


@dataclass(frozen=True)
class Commit:
    """커밋 노드 하나.

    hash      : 세션 내 유일한 식별자 (고정 길이 16진수)
    message   : 커밋 메시지
    author    : 작성자
    timestamp : 생성 시각
    parents   : 부모 커밋 hash 튜플 (첫 커밋 0개, 일반 1개, merge 2개)
    seq       : 생성 순번 — 같은 초에 만들어진 커밋의 동률을 깨는 데 쓴다
    """

    hash: str
    message: str
    author: str
    timestamp: datetime
    parents: tuple = field(default_factory=tuple)
    seq: int = 0

    def time_str(self):
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")


class CommitStore:
    """hash → Commit 해시맵. 조회·존재 확인 모두 평균 O(1).

    hash 생성도 여기서 책임진다: 내용으로 SHA-1 을 만들고 앞 7자리를 쓴다.
    7자리(16^7 ≈ 2.7억)라도 충돌은 0 이 아니므로, 이미 있는 hash 면
    nonce 를 올려 다시 만든다 → **중복이 생길 수 없음을 코드로 보장**.
    단, 공간(16^7 개)이 남아 있는 한이다. 꽉 차면 재생성 루프가 끝나지 않으므로 먼저 막는다.
    """

    def __init__(self):
        self._commits = {}
        self._next_seq = 0

    def __contains__(self, commit_hash):
        return commit_hash in self._commits

    def __len__(self):
        return len(self._commits)

    def get(self, commit_hash):
        """없으면 None."""
        return self._commits.get(commit_hash)

    def all(self):
        """생성 순서대로 모든 커밋 (dict 는 삽입 순서를 기억한다)."""
        return list(self._commits.values())

    def create(self, message, author, timestamp, parents=()):
        """새 커밋을 만들어 저장하고 돌려준다. 부모가 없으면 ValueError."""
        for parent in parents:
            if parent not in self._commits:
                raise ValueError(f"unknown parent: {parent}")
        if len(self._commits) >= 16 ** HASH_LENGTH:
            raise HashSpaceExhausted(f"hash space exhausted: {len(self._commits)} commits")
        seq = self._next_seq
        commit_hash = self._make_hash(message, author, timestamp, parents, seq)
        commit = Commit(commit_hash, message, author, timestamp, tuple(parents), seq)
        self._commits[commit_hash] = commit
        self._next_seq += 1
        return commit

    def _make_hash(self, message, author, timestamp, parents, seq):
        nonce = 0
        while True:
            payload = "\0".join(
                [str(seq), author, message, timestamp.isoformat(), ",".join(parents), str(nonce)]
            )
            candidate = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:HASH_LENGTH]
            if candidate not in self._commits:
                return candidate
            nonce += 1
