# minigit · Mini Git

**커밋 DAG · 위상 정렬 · BFS 최단 경로 · 직접 구현한 정렬 · 역색인으로 만든 CLI 버전 관리 흉내.**
파일 내용은 추적하지 않고, 커밋 메타데이터(hash / message / author / timestamp / parents)만 메모리에서 다룬다.
`sorted()` / `list.sort()` / 그래프 라이브러리는 쓰지 않는다.

| 기간 | 역할 | 스택 | 결과 |
|---|---|---|---|
| 2026.10 | 1인 개발 | Python 3.10+ (표준 라이브러리) | 테스트 37개 |

---

## 빠른 시작

```bash
python main.py                          # REPL 시작 (mini-git> 프롬프트)
python main.py < demo/example.txt       # 기본 예시 시나리오
python main.py < demo/script.txt        # merge·orphan·에러까지 포함한 긴 시나리오
python -m unittest discover -s tests -v # 테스트
python bench_sort.py                    # 정렬 알고리즘 성능 비교
python demo-setting.py --shell          # 시연용 이력(A~M2)을 깔고 바로 REPL
```

## 실행 예시

`python main.py --fixed-clock < demo/example.txt` 의 출력이다(빈 줄은 뺐다).

```text
mini-git> init "Ari"
Initialized repository.
Current branch: main
Current user: Ari
mini-git> commit "Set up project"
[main 4280179] Set up project
mini-git> branch feature
Created branch: feature
mini-git> switch feature
Switched to branch: feature
mini-git> commit "Add signup feature"
[feature 1cdd61f] Add signup feature
mini-git> switch main
Switched to branch: main
mini-git> commit "Add cart feature"
[main 7333cf5] Add cart feature
mini-git> log
commit 4280179 (Ari, 2025-03-10 09:00:00)
    Set up project
commit 1cdd61f (Ari, 2025-03-10 09:15:00) [feature]
    Add signup feature
commit 7333cf5 (Ari, 2025-03-10 09:30:00) [HEAD -> main]
    Add cart feature
mini-git> path feature main
Path: 1cdd61f -> 4280179 -> 7333cf5 (2 edges)
mini-git> search "signup"
Found 1 commit:
- 1cdd61f: Add signup feature
mini-git> merge feature
[main 70cfbfe] Merge branch 'feature' into main
Merge: 7333cf5 1cdd61f
mini-git> ancestors HEAD
Ancestors of HEAD (3 commits):
- 7333cf5: Add cart feature
- 1cdd61f: Add signup feature
- 4280179: Set up project
mini-git> exit
Bye.
```

hash 는 내용 + 시각으로 만들기 때문에 실행할 때마다 달라진다.
그래서 커밋 인자 자리에는 **브랜치 이름이나 `HEAD`** 도 쓸 수 있게 했다 (`path feature main`, `ancestors HEAD`).

---

## 명령어

명령어는 대소문자를 구분하지 않는다. 공백이 들어간 인자는 따옴표로 감싼다(`commit "Add signup"`).
따옴표를 빼먹어도 문자열 인자(사용자명·메시지·키워드)는 나머지 단어를 이어 붙여 받아준다.

| 명령 | 동작 | 출력 |
|---|---|---|
| `INIT <user_name>` | 저장소 초기화, `main` 브랜치 + HEAD, 현재 사용자 설정. 다시 실행하면 이력은 두고 사용자만 바꿈 | `Initialized repository.` / 브랜치 / 사용자 |
| `BRANCH <name>` | HEAD 커밋을 가리키는 새 브랜치 (이동은 안 함) | `Created branch: <name>` |
| `BRANCH` | 브랜치 목록 (`*` = 현재) | |
| `SWITCH <name>` | HEAD 를 그 브랜치로 | `Switched to branch: <name>` |
| `SWITCH --orphan <name>` | 부모 없는 새 브랜치로 이동 (새 루트를 만들어 `No path` 상황 재현용) | |
| `COMMIT <message>` | HEAD 를 부모로 새 커밋, 브랜치 전진, 역색인 갱신 | `[<branch> <hash>] <message>` |
| `COMMIT --date="YYYY-MM-DD HH:MM:SS" <message>` | 시각을 직접 지정 (`git commit --date`). 시계가 틀린 커밋을 재현해 LOG 가 관계로 정렬함을 보이는 용도 | |
| `LOG` | **부모가 항상 자식보다 먼저** (위상 정렬) | `commit <hash> (<author>, <time>) [<branches>]` + 메시지 |
| `LOG --sort-by=date\|author` | 시각 / 작성자 기준 정렬 (동률은 위상 순서 유지) | |
| `LOG ... --algo=merge\|quick\|heap\|insertion` | 정렬 알고리즘 교체 (기본 merge) | |
| `PATH <c1> <c2>` | 무방향 최단 경로, 동률이면 사전순 최소 | `Path: a -> b -> c (2 edges)` / `No path` |
| `ANCESTORS <commit>` | 도달 가능한 모든 조상 (가까운 세대부터) | `Ancestors of <c> (N commits):` + 목록 |
| `SEARCH <keyword>` | 메시지에 키워드가 있는 커밋 (여러 단어면 모두 포함 = AND) | `Found N commits:` + 목록 |
| `SEARCH --author=<name>` | 작성자의 커밋 (대소문자 무시) | |
| `MERGE <branch> [<message>]` | 부모 2개인 merge 커밋 | `[main <hash>] Merge ...` + `Merge: p1 p2` |
| `DIFF <file1> <file2>` | 줄 단위 비교 — `  ` 공통 / `- ` 삭제 / `+ ` 추가 | |
| `HELP` / `EXIT` / `QUIT` | 도움말 / 종료 (Ctrl-D, Ctrl-C 도 종료) | |
| `# ...` | 주석 줄 — 무시 (시연 스크립트용) | |

`python main.py --fixed-clock` 은 시계를 고정한다(2025-03-10 09:00:00 부터 커밋마다 15분). 시각이 hash 재료라서 hash 가 매번 같아진다.

### 에러 메시지

| 상황 | 메시지 |
|---|---|
| 인자 개수·형식이 틀림, 빈 메시지, 알 수 없는 옵션 | `Invalid args` |
| 따옴표가 안 닫힘 | `Invalid args (unclosed quote)` |
| 없는 브랜치 | `Unknown branch: <name>` |
| 없는 커밋 | `Unknown commit: <hash>` |
| 없는 명령 | `Unknown command: <cmd>` |
| INIT 전에 다른 명령 | `Not a repository. Run: INIT <user_name>` |
| 첫 커밋 전에 BRANCH | `No commits yet` |
| 이미 있는 브랜치 | `Branch already exists: <name>` |

---

## 설계

```
main.py              REPL 루프 (읽기 → 실행 → 출력 → 반복)
minigit/
├── cli.py           토큰 분리(shlex) · 명령 디스패치 · 출력 문자열      ← 사람이 읽는 형식은 여기만
├── repository.py    브랜치 · HEAD · 사용자 · 명령별 동작                ← 알고리즘을 '호출' 만 한다
├── commit.py        Commit 노드 + CommitStore(hash → Commit 해시맵)
├── graph.py         위상 정렬(Kahn) · 무방향 최단 경로(BFS) · 조상(BFS)  ← 탐색
├── sorting.py       병합 · 퀵 · 힙 · 삽입 정렬 + MinHeap                ← 정렬
├── index.py         역색인 (keyword → hashes, author → hashes)          ← 인덱싱
└── diff.py          LCS 줄 단위 diff
bench_sort.py        정렬 성능 비교
tests/               unittest 37개
demo/                example.txt(기본 예시) · script.txt(전체 기능·에러) · features·structure·concepts·whatif(시연)
demo-setting.py      라이브 데모용 이력을 미리 깔아 둔다 (--shell)
docs/                설명 그림 7장 + make_figures.py · graph_demo.py(경로 탐색 대조 실험)
```

알고리즘 함수(`graph.py`, `sorting.py`, `index.py`)는 저장소 클래스를 모른다.
`graph.py` 의 함수는 `{hash: (부모, ...)}` 딕셔너리 하나만 받기 때문에, 손으로 만든 작은 그래프로 바로 테스트된다.

대가: `LOG` · `PATH` · `ANCESTORS` · `MERGE` 는 호출할 때마다 `parents_map()` 을 새로 만든다(O(V)). 각 명령의 Big-O(O(V+E))는
그대로지만, MERGE 는 조상 집합 전체를 구하므로 커밋 수에 비례한다 — 실측 V=1,000 에서 0.15ms, 10만에서 22.6ms (COMMIT 은 약 2.6μs).
메모리 상 세션 규모에서는 단순함을 택했다.

```
             branches (이름표)            CommitStore (해시맵)
HEAD ──▶ "main"   ──▶ 70cfbfe ──parents──▶ 7333cf5 ──▶ 4280179
         "feature"──▶ 1cdd61f ──parents──────────────▶ 4280179
                          ▲
                  70cfbfe 의 두 번째 부모 (merge)
```

---

## 핵심 개념 5가지

### 1. 커밋 그래프는 왜 DAG 인가

- **방향(Directed)**: 간선은 "자식 → 부모" 한 방향으로만 저장한다. 커밋은 자기 부모만 알고, 자식은 모른다.
- **비순환(Acyclic)**: 새 커밋의 부모는 **이미 존재하는** 커밋뿐이고, 커밋은 만들어진 뒤 바뀌지 않는다(`frozen=True`).
  그러니 간선은 언제나 "새 노드 → 옛 노드" 로만 생긴다. 사이클이 생기려면 옛 커밋이 새 커밋을 부모로 가져야 하는데,
  옛 커밋은 수정할 수 없으므로 불가능하다. (실제 Git 에서는 부모 hash 가 자식 hash 의 재료라서, 부모가 자식을 가리키려면
  아직 정해지지 않은 hash 를 알아야 한다 — 같은 이유다.)
- **트리가 아닌 이유**: merge 커밋은 부모가 2개다. 한 노드에 부모가 여럿이면 트리가 아니라 그래프다.

`topological_order()` 는 모든 노드를 내보내지 못하면 `cycle detected` 를 낸다 — DAG 가 깨지면 바로 알 수 있다.

### 2. LOG — "부모가 먼저" 를 보장하는 위상 정렬 (Kahn 알고리즘)

"최신순" 은 시각을 보지만, 시각은 믿을 수 없다(시계가 틀린 컴퓨터, 같은 초에 만든 커밋).
LOG 가 지켜야 하는 것은 **관계**다: 어떤 커밋이 나오기 전에 그 부모가 전부 나와 있어야 한다. 이것이 위상 정렬의 정의다.

1. 각 커밋의 "아직 안 나온 부모 수" 를 센다.
2. 그 수가 0 인 커밋(루트)을 '준비됨' 에 넣는다.
3. 준비된 것 하나를 출력하고, 그 자식들의 수를 1 줄인다. 0 이 된 자식을 준비됨에 넣는다. 반복.

준비된 커밋이 여럿일 때 무엇을 먼저 낼지는 위상 정렬이 정해주지 않는다. 그래서 **생성 순번(seq)이 작은 것부터** 꺼내도록
직접 만든 최소 힙을 썼다 → 항상 같은 순서(결정적). 복잡도 O((V+E) log V).

> 관찰: 이 프로그램에서는 부모가 항상 자식보다 먼저 만들어지므로 '생성 순서' 자체가 이미 위상 순서다.
> 그래도 Kahn 을 쓴 이유는 그 성질을 **가정하지 않고 계산하기** 위해서다 — 커밋을 가져오거나(fetch) 재배열(rebase)하면
> 생성 순서와 그래프 순서가 어긋난다.

### 3. PATH — 무방향 BFS + 사전순 최소 경로

간선 가중치가 모두 1 이면 BFS 가 처음 닿은 거리가 최단 거리다. 문제는 **최단 경로가 여러 개일 때 사전순 최소**를 고르는 것.

1. **목적지에서** BFS 를 돌려 모든 노드의 "목적지까지 남은 거리" 를 구한다.
2. 출발지에서 시작해, 매 걸음 **남은 거리가 정확히 1 줄어드는 이웃 중 hash 가 가장 작은 것**으로 간다.

왜 욕심(greedy)이 맞나: 최단 경로들은 길이가 같고, 문자열 사전순 = 앞 칸부터 hash 를 비교한 순서다.
앞 칸에서 더 작은 것을 고르면 뒤가 무엇이든 그 경로가 이긴다. '남은 거리 −1' 인 이웃만 고르므로 막다른 길도 없다.
O(V+E). 출발지에서 BFS 하며 **이웃을 작은 순서로 방문**해 '처음 발견한 부모' 를 기록하는 방법도 정답이다
(같은 층 안의 큐 순서가 곧 경로의 사전순이 된다). 단 노드마다 이웃 정렬이 필요하고, 이웃 순서를 정하지 않으면(set 순회)
최단이지만 사전순이 틀린다 — 무작위 DAG 약 2,850쌍에서 약 240~290건 오답(PYTHONHASHSEED 에 따라 변동) (`python docs/graph_demo.py`).
목적지 BFS + 욕심 방식은 정렬 없이 이웃 중 최솟값 하나만 찾으면 된다.

테스트(`test_shortest_path_matches_brute_force`)는 무작위 작은 DAG 60개에서 **모든 단순 경로를 나열한 정답**과 비교한다.

'문자열 사전순 = 칸별 비교' 는 hash 길이가 같으면 자명하다. 길이가 달라도 `"ab->…"` vs `"abc->…"` 에서
구분자 `-`(0x2D) 가 어떤 16진수 글자(`0`=0x30 이상)보다 작아서 결과는 같다 — 무작위 가변 길이 16진수 경로 2만 쌍에서 불일치 0.
어긋나는 건 `-` 보다 작은 글자(`+`, 공백 등)가 식별자에 섞일 때뿐이다. 그래도 길이를 고정해 이 논증 자체가 필요 없게 했다.

### 4. ANCESTORS — BFS + 방문 집합

부모 방향으로만 BFS. merge 커밋이 있으면 같은 조상에 두 갈래로 닿는데(다이아몬드), **방문 집합이 없으면 그 조상과 그 위가 전부 중복 출력**된다.
`seen` 집합으로 각 커밋을 한 번만 넣어 O(V+E). 출력은 가까운 세대부터.

### 5. 정렬 — 직접 구현 4종

| 알고리즘 | 평균 | 최악 | 추가 메모리 | 안정 |
|---|---|---|---|---|
| 병합 정렬 (기본) | O(n log n) | O(n log n) | O(n) | **예** |
| 퀵 정렬 (무작위 피벗 · 3-way) | O(n log n) | O(n²) | O(log n) — 큰 쪽을 미루고 작은 쪽 먼저 | 아니오 |
| 힙 정렬 | O(n log n) | O(n log n) | O(1)* | 아니오 |
| 삽입 정렬 | O(n²) | O(n²) | O(1)* | **예** |

\* 교과서 기준(제자리). 이 구현은 원본 리스트를 보존하려고 복사본을 만들기 때문에 실제로는 O(n).

**안정 정렬**은 "키가 같은 원소끼리 원래 순서를 지킨다" 는 뜻이다. `LOG --sort-by=author` 는 **위상 순서를 입력으로** 넣고
병합 정렬을 쓰므로, 같은 작성자의 커밋은 부모가 먼저인 순서가 그대로 남는다. 즉 "작성자로 묶고, 묶음 안에서는 이력 순서" 가
정렬 기준 하나만으로 공짜로 나온다. `--algo=quick` 을 주면 이 순서가 섞이는 것을 직접 볼 수 있다.

비교 기준 교체는 `key` 함수로 한다: `merge_sort(commits, key=lambda c: c.timestamp)`.

#### 성능 비교 (`python bench_sort.py`, 단위 ms, 3회 중 최솟값)

| 입력 | n | merge | quick | heap | insertion |
|---|---:|---:|---:|---:|---:|
| random | 1,000 | 0.91 | 1.06 | 1.54 | 14.59 |
| sorted | 1,000 | 0.61 | 1.05 | 1.41 | **0.09** |
| random | 10,000 | 12.06 | 14.58 | 22.12 | **1654.02** |
| sorted | 10,000 | 8.50 | 15.10 | 21.47 | **1.15** |
| few-keys | 10,000 | 11.59 | **2.50** | 18.14 | 1274.93 |
| random | 50,000 | 78.69 | 93.69 | 141.74 | – |
| sorted | 50,000 | 46.14 | 92.04 | 133.04 | – |
| few-keys | 50,000 | 70.37 | **11.03** | 111.64 | – |

- **삽입 정렬**: n 이 10배 → 시간 약 100배 (14.6ms → 1654ms) = O(n²). 그런데 **이미 정렬된 입력에서는 1.15ms** — 약 1,400배 빠르다(최선 O(n)).
- **퀵 정렬 3-way**: 값 종류가 5개뿐인 입력에서 병합보다 4.5~6.5배 빠르다. 같은 값을 한 번에 확정하기 때문 — 작성자 정렬이 정확히 이런 입력이다.
- **힙 정렬**: 같은 O(n log n) 인데 가장 느리다. 배열을 멀리 뛰어다니며 비교해 상수가 크다.
- 결론: 기본값은 **안정성이 필요해서** 병합 정렬. 속도만 보면 동률 많은 입력에선 3-way 퀵이 낫지만 동률 순서를 보장하지 못한다.

### 6. 역색인 — 순회 검색보다 빠른 이유

```
keyword 인덱스                      author 인덱스
"add"     → [1cdd61f, 7333cf5]       "ari" → [4280179, 1cdd61f, 7333cf5]
"signup"  → [1cdd61f, 8c3237f]       "ben" → [8c3237f, c53edb2]
"cart"    → [7333cf5]
```

| 방식 | 검색 1회 비용 | 비고 |
|---|---|---|
| 순회 검색 | O(N × L) | 커밋 N 개의 메시지(길이 L)를 전부 split 하고 비교 |
| 역색인 | O(1) + O(k) | 해시맵에서 키 찾기 + 결과 k 개 꺼내기. **N 과 무관** |
| 역색인 갱신 | 커밋당 O(m) | 메시지 토큰 수 m 만큼 목록에 추가 |

비용을 '쓸 때(커밋)' 미리 내고 '읽을 때(검색)' 아낀다. 여러 단어 검색은 각 목록의 교집합(AND)이며,
가장 짧은 목록을 기준으로 나머지를 set 으로 확인해 O(가장 짧은 목록 + 나머지 목록 길이 합) — 역시 N 과 무관하다.

토큰 규칙: 최소 기준(공백 split + lower)에 **양 끝 문장부호 제거**를 더했다.
안 하면 `"Fix signup, signout"` 의 토큰이 `signup,` 이 되어 `SEARCH signup` 에 안 걸린다. 가운데 문장부호(`e-mail`, `v1.2`)는 남긴다.

---

## 구현 선택

| 항목 | 선택 | 이유 |
|---|---|---|
| hash | `sha1(순번·작성자·메시지·시각·부모·nonce)` 앞 7자리, 이미 있으면 nonce+1 로 재생성 | 실제 Git 처럼 내용 기반. 충돌을 '확률이 낮다' 가 아니라 **재생성으로 0** 으로 만든다 (1자리로 줄여 강제 충돌시키는 테스트 있음) |
| hash 길이 고정 | 충돌 시 길이를 늘리지 않고 다시 만듦. 공간이 꽉 차면 무한 루프 대신 `Repository full: …` 로 그 커밋만 거부 | PATH 사전순을 '칸별 비교' 로 바로 읽을 수 있게 (16진수라 길이가 달라도 결과는 같지만, 논증을 없앰) |
| 커밋 인자 | 정확한 hash → 브랜치 이름 → `HEAD` 순으로 해석 | hash 가 실행마다 바뀌어도 데모·테스트가 가능 |
| LOG 범위 | 저장소의 **모든** 커밋 (모든 브랜치) | 예시처럼 다른 브랜치 커밋도 보여야 해서 |
| LOG 동률 | 동시에 준비된 커밋은 생성순 | 결정적 출력 |
| `--sort-by=date` 동률 | 위상 순서 유지 (안정 정렬) | 같은 초에 만든 커밋도 부모가 먼저 |
| `--sort-by=author` | 대소문자 무시, 동률은 위상 순서 | |
| 브랜치 표시 | `[HEAD -> main, feature]` 처럼 **브랜치 끝(tip)** 에만 | 실제 Git 의 `--decorate` 와 같음. 브랜치는 '커밋이 만들어진 곳' 이 아니라 '지금 가리키는 곳' 이다 |
| 재-INIT | 이력 유지, 사용자만 변경 | 실제 `git init` 도 기존 이력을 지우지 않음. 여러 작성자 시나리오에 필요 |
| 첫 커밋 전 BRANCH | `No commits yet` | 가리킬 커밋이 없음 (Git 도 거부) |
| MERGE | 대상이 이미 조상이면 `Already up to date.`, 아니면 항상 merge 커밋 (`--no-ff`). 커밋 없는(orphan 직후) 브랜치에서는 `No commits yet` (Git 은 허용) | merge 는 부모 2개인 커밋으로 남긴다 |
| `No path` | `SWITCH --orphan` 으로 새 루트를 만들면 재현됨 | 루트가 하나면 무방향 그래프는 항상 연결되어 있다 |

## 직접 구현 원칙

| 원칙 | 확인 방법 |
|---|---|
| `sorted()` / `list.sort()` 금지 | `test_no_standard_sort_api_in_source` 가 AST 로 minigit · tests · demo · docs · main · bench 의 모든 호출을 검사 |
| 그래프 라이브러리 금지 | `dict` / `list` / `set` 만 사용. 큐도 `deque` 대신 list + 읽기 위치 |
| 해시맵 기반 조회 | `CommitStore` 는 `dict` (평균 O(1)) |
| 알고리즘 분리 | 탐색 `graph.py` · 정렬 `sorting.py` · 인덱싱 `index.py` |
| 주석·docstring | 모든 모듈·주요 클래스·함수 |

## 테스트

```bash
python -m unittest discover -s tests -v
```

정렬(정확성·안정성·불안정성·입력 보존·최악 입력), 그래프(무작위 DAG 30개 위상 검증, 사이클 탐지, 최단 경로 브루트포스 대조 60개,
조상 = 도달 가능 집합), 해시 강제 충돌, 역색인, CLI(예시 시나리오·대소문자·따옴표·표준 에러·merge·diff), 퀵 정렬 최악 피벗에서의 스택 깊이 37개.

## 문서

| 문서 | 내용 |
|---|---|
| [demo/](demo/README.md) | 시연 스크립트 (`features.txt` · `structure.py` · `concepts.py` · `whatif.py`) |
| [docs/](docs/) | 그림 7장 — [커밋 그래프](docs/commit-graph.png) · [LOG 순서](docs/log-orders.png) · [Kahn 단계](docs/kahn-steps.png) · [PATH BFS](docs/path-bfs.png) · [ANCESTORS](docs/ancestors-seen.png) · [역색인](docs/inverted-index.png) · [구조](docs/architecture.png) (`python3 docs/make_figures.py` 로 다시 생성) |
