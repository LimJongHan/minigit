"""역색인(Inverted Index) — '단어 → 그 단어가 나온 커밋 목록'.

책 뒤의 '찾아보기' 와 같다. 본문을 처음부터 읽는 대신(순회 검색, O(N × 메시지 길이)),
단어를 찾아보기에서 찾고(해시맵, 평균 O(1)) 적힌 쪽수만 펼친다(결과 개수 k, O(k)).

비용은 '쓸 때' 낸다: 커밋할 때마다 메시지의 토큰 수 m 만큼 목록에 추가(O(m)).
읽기가 쓰기보다 훨씬 잦은 검색에서 이 거래가 남는 장사다.
"""

import string

_EDGE_PUNCT = string.punctuation + "“”‘’"


def tokenize(text):
    """메시지 → 키워드 목록.

    최소 기준: 공백으로 split 하고 lower 로 정규화.
    추가 규칙 하나: 토큰 양 끝의 문장부호를 떼어낸다 ("signup," → "signup").
    안 떼면 `SEARCH signup` 이 "Fix signup, signout" 을 놓친다.
    가운데 문장부호(예: "e-mail", "v1.2") 는 남긴다.
    """
    tokens = []
    for raw in text.lower().split():
        token = raw.strip(_EDGE_PUNCT)
        if token:
            tokens.append(token)
    return tokens


def normalize_author(name):
    """작성자 키: 앞뒤 공백 제거 + 소문자 (`--author=ari` 도 Ari 를 찾는다)."""
    return " ".join(name.split()).lower()


class InvertedIndex:
    """키 → [commit_hash, ...] 해시맵. 목록은 커밋 생성 순서를 유지한다.

    같은 메시지에 같은 단어가 두 번 나와도 그 커밋은 한 번만 기록한다
    (posting 마지막 원소만 보면 되므로 O(1) 확인 — 커밋은 한 번에 하나씩 추가되기 때문).
    """

    def __init__(self):
        self._postings = {}

    def add(self, key, commit_hash):
        posting = self._postings.setdefault(key, [])
        if not posting or posting[-1] != commit_hash:
            posting.append(commit_hash)

    def get(self, key):
        """키가 없으면 빈 리스트. 원본 보호를 위해 복사본을 준다."""
        return list(self._postings.get(key, ()))

    def keys(self):
        return list(self._postings)

    def __len__(self):
        return len(self._postings)


class CommitIndex:
    """2종 인덱스를 함께 관리: keyword → hashes, author → hashes."""

    def __init__(self):
        self.keywords = InvertedIndex()
        self.authors = InvertedIndex()

    def add_commit(self, commit):
        for token in tokenize(commit.message):
            self.keywords.add(token, commit.hash)
        self.authors.add(normalize_author(commit.author), commit.hash)

    def search_keyword(self, query):
        """쿼리의 모든 토큰을 포함하는 커밋 (AND). 단어 하나면 그 posting 그대로.

        교집합은 '가장 짧은 posting' 을 기준으로 나머지를 set 으로 확인한다.
        → O(가장 짧은 목록 + 나머지 목록 길이 합). 전체 커밋 수 N 과 무관.
        """
        tokens = tokenize(query)
        if not tokens:
            return []
        postings = [self.keywords.get(token) for token in tokens]
        shortest = postings[0]
        for posting in postings[1:]:
            if len(posting) < len(shortest):
                shortest = posting
        others = [set(posting) for posting in postings if posting is not shortest]
        return [h for h in shortest if all(h in other for other in others)]

    def search_author(self, name):
        return self.authors.get(normalize_author(name))
