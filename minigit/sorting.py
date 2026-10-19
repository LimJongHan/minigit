"""정렬 알고리즘 직접 구현 — `sorted()` / `list.sort()` 를 쓰지 않는다.

모든 함수는 같은 모양이다:

    algo(items, key=None, reverse=False) -> 새 리스트

- 원본 리스트는 건드리지 않는다(새 리스트를 돌려준다).
- `key` 는 "무엇을 기준으로 비교할지"를 바꾸는 함수다. 날짜 기준이면
  `key=lambda c: c.timestamp`, 작성자 기준이면 `key=lambda c: c.author`.
- `reverse=True` 는 내림차순. 안정 정렬에서도 동률끼리의 원래 순서는 유지된다.

| 알고리즘        | 평균        | 최악        | 추가 메모리 | 안정? |
|-----------------|-------------|-------------|-------------|-------|
| merge_sort      | O(n log n)  | O(n log n)  | O(n)        | 예    |
| quick_sort      | O(n log n)  | O(n^2)      | O(log n)*   | 아니오 |
| heap_sort       | O(n log n)  | O(n log n)  | O(1)**      | 아니오 |
| insertion_sort  | O(n^2)      | O(n^2)      | O(1)**      | 예    |

 *  재귀 대신 명시적 스택. 큰 쪽을 스택에 미루고 작은 쪽을 먼저 처리해서 최악에도 O(log n).
 ** 이 구현은 원본을 보존하려고 복사본을 만들기 때문에 실제로는 O(n).
"""

import random


def _identity(x):
    return x


def _prepare(items, key):
    """(키, 값) 묶음을 만든다. 비교는 언제나 키([0]) 로만 한다.

    키를 미리 한 번만 계산해두면(decorate) 비교할 때마다 key() 를 다시 부르지 않는다.
    """
    key = key or _identity
    return [(key(item), item) for item in items]


def _less(a, b, reverse):
    """정렬 방향을 반영한 '앞에 와야 하는가' 비교. 동률이면 항상 False."""
    return a > b if reverse else a < b


# ============================================================== 병합 정렬 (안정)
def merge_sort(items, key=None, reverse=False):
    """병합 정렬 — 반으로 쪼개서 각각 정렬한 뒤, 앞에서부터 하나씩 비교하며 합친다.

    합칠 때 두 값이 같으면 **왼쪽(원래 앞에 있던 것)을 먼저** 꺼낸다.
    오른쪽이 '확실히 앞' 일 때만 오른쪽을 꺼내는 이 규칙이 안정 정렬을 만든다
    (`_less(right, left)` 를 `right <= left` 로 바꾸면 깨진다 — 동률에서 오른쪽이 먼저 나가기 때문).
    시간: 항상 O(n log n) — 쪼개는 깊이 log n × 깊이마다 합치는 비용 n.
    """
    pairs = _prepare(items, key)
    return [item for _, item in _merge_sort_pairs(pairs, reverse)]


def _merge_sort_pairs(pairs, reverse):
    if len(pairs) <= 1:
        return pairs
    mid = len(pairs) // 2
    left = _merge_sort_pairs(pairs[:mid], reverse)
    right = _merge_sort_pairs(pairs[mid:], reverse)

    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        # 오른쪽이 '확실히 앞'일 때만 오른쪽을 꺼낸다 → 동률이면 왼쪽 우선 = 안정
        if _less(right[j][0], left[i][0], reverse):
            merged.append(right[j])
            j += 1
        else:
            merged.append(left[i])
            i += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


# ============================================================== 퀵 정렬 (불안정)
def quick_sort(items, key=None, reverse=False, rng=None):
    """퀵 정렬 — 기준값(pivot)을 하나 골라 '작은 것 | 같은 것 | 큰 것' 으로 나눈다.

    - 피벗을 무작위로 골라 '이미 정렬된 입력 → O(n^2)' 함정을 확률적으로 피한다.
      (피벗을 항상 맨 앞으로 고르면 정렬된 입력에서 매번 한쪽이 텅 비어 n^2 가 된다.)
    - 3-way 분할: 같은 값이 많을 때(작성자 기준 정렬처럼) 그 값들을 한 번에 확정한다.
    - 제자리 교환을 하므로 같은 키의 원래 순서가 섞인다 → **불안정**.
    """
    rng = rng or random.Random(0)
    arr = _prepare(items, key)

    lo, hi = 0, len(arr) - 1
    stack = [(lo, hi)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            lt, gt = _partition3(arr, lo, hi, reverse, rng)
            # 큰 구간은 스택에 미루고 작은 구간을 바로 이어서 처리 → 스택 깊이 O(log n)
            # (지금 처리하는 쪽이 매번 절반 이하로 줄어야 미뤄둔 구간이 log n 개를 넘지 않는다.
            #  반대로 하면 피벗이 계속 나쁠 때 스택이 n 에 비례해 쌓인다 — 실측 n=3000 에서 100개 이상 vs 4개,
            #  README 의 퀵 정렬 절 참고)
            if lt - lo < hi - gt:
                stack.append((gt + 1, hi))
                hi = lt - 1
            else:
                stack.append((lo, lt - 1))
                lo = gt + 1
    return [item for _, item in arr]


def _partition3(arr, lo, hi, reverse, rng):
    """Dijkstra 3-way 분할. arr[lo:lt] < pivot == arr[lt:gt+1] < arr[gt+1:hi+1]."""
    p = rng.randint(lo, hi)
    arr[lo], arr[p] = arr[p], arr[lo]
    pivot = arr[lo][0]
    lt, i, gt = lo, lo + 1, hi
    while i <= gt:
        k = arr[i][0]
        if _less(k, pivot, reverse):
            arr[lt], arr[i] = arr[i], arr[lt]
            lt += 1
            i += 1
        elif _less(pivot, k, reverse):
            arr[i], arr[gt] = arr[gt], arr[i]
            gt -= 1
        else:
            i += 1
    return lt, gt


# ============================================================== 힙 정렬 (불안정)
class MinHeap:
    """배열 기반 이진 최소 힙. 힙 정렬과 LOG 의 위상 정렬(Kahn) 에서 함께 쓴다.

    i 번 노드의 자식은 2i+1, 2i+2, 부모는 (i-1)//2.
    push / pop 모두 O(log n), 가장 작은 값 보기는 O(1).
    """

    def __init__(self, less=None):
        self._data = []
        self._less = less or (lambda a, b: a < b)

    def __len__(self):
        return len(self._data)

    def push(self, value):
        data = self._data
        data.append(value)
        i = len(data) - 1
        while i > 0:  # 위로 올리기(sift up)
            parent = (i - 1) // 2
            if not self._less(data[i], data[parent]):
                break
            data[i], data[parent] = data[parent], data[i]
            i = parent

    def pop(self):
        data = self._data
        if not data:
            raise IndexError("pop from empty heap")
        top = data[0]
        last = data.pop()
        if data:
            data[0] = last
            self._sift_down(0)
        return top

    def _sift_down(self, i):
        data, n = self._data, len(self._data)
        while True:
            left, right, smallest = 2 * i + 1, 2 * i + 2, i
            if left < n and self._less(data[left], data[smallest]):
                smallest = left
            if right < n and self._less(data[right], data[smallest]):
                smallest = right
            if smallest == i:
                return
            data[i], data[smallest] = data[smallest], data[i]
            i = smallest


def heap_sort(items, key=None, reverse=False):
    """힙 정렬 — 전부 힙에 넣고 가장 작은 것부터 하나씩 꺼낸다.

    항상 O(n log n) 이지만, 힙 안에서 자리 교환이 멀리 일어나 **불안정**하다.
    """
    pairs = _prepare(items, key)
    heap = MinHeap(less=lambda a, b: _less(a[0], b[0], reverse))
    for pair in pairs:
        heap.push(pair)
    return [heap.pop()[1] for _ in range(len(pairs))]


# ============================================================== 삽입 정렬 (안정)
def insertion_sort(items, key=None, reverse=False):
    """삽입 정렬 — 카드 정리하듯 하나씩 꺼내 '이미 정렬된 앞부분' 의 제자리에 끼운다.

    거의 정렬된 입력이면 O(n) 에 가깝게 빠르지만 일반적으로 O(n^2).
    자기보다 '확실히 큰' 것만 밀어내므로 동률의 순서는 유지된다 → **안정**.
    """
    arr = _prepare(items, key)
    for i in range(1, len(arr)):
        current = arr[i]
        j = i - 1
        while j >= 0 and _less(current[0], arr[j][0], reverse):
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = current
    return [item for _, item in arr]


ALGORITHMS = {
    "merge": merge_sort,
    "quick": quick_sort,
    "heap": heap_sort,
    "insertion": insertion_sort,
}
