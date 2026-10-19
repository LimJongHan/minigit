"""줄 단위 diff — 최장 공통 부분 수열(LCS) 동적 계획법.

두 파일에서 '순서를 유지한 채 공통으로 남길 수 있는 줄' 을 최대로 고르면,
나머지는 자연스럽게 '삭제된 줄(-)' 과 '추가된 줄(+)' 이 된다.

dp[i][j] = a[i:] 와 b[j:] 의 LCS 길이.  시간·공간 O(n × m).
(실제 Git 은 더 빠른 Myers 알고리즘 O((n+m)·D) 를 쓴다. D = 바뀐 줄 수.)
"""


def lcs_table(a, b):
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a[i] == b[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return dp


def diff_lines(a, b):
    """[(tag, line), ...]  tag: ' ' 공통, '-' a 에만(삭제), '+' b 에만(추가).

    동률일 때 삭제를 먼저 내보낸다 → 바뀐 줄이 '-옛줄 / +새줄' 순으로 붙어 나온다.
    """
    dp = lcs_table(a, b)
    i = j = 0
    result = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            result.append((" ", a[i]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            result.append(("-", a[i]))
            i += 1
        else:
            result.append(("+", b[j]))
            j += 1
    result.extend(("-", line) for line in a[i:])
    result.extend(("+", line) for line in b[j:])
    return result


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()
