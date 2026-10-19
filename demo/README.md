# 시연 스크립트

기능·구조·개념·가정을 실제로 돌려 보는 스크립트 모음이다. 모두 저장소 루트에서 실행한다.

| 파일 | 실행 | 내용 |
|---|---|---|
| `features.txt` | `python3 main.py --fixed-clock < demo/features.txt` | 기능 전부 + 표준 에러 (기대 출력 `features.out`) |
| `structure.py` | `python3 demo/structure.py` | 구조 — 내부 상태 · 해시맵/충돌 · 역색인 갱신 · 탐색 재사용 · docstring 커버리지 |
| `concepts.py` | `python3 demo/concepts.py` | 개념 — 사이클 반례 · Kahn 한 걸음씩 · BFS vs DFS · 무방향 이유 · 비교 횟수 · 역색인 |
| `whatif.py` | `python3 demo/whatif.py` | 가정 — 10배 실측과 개선안 3개 · 부모 방향 PATH · 위상 유지 author 정렬 · hash 방식 |
| `scenario.py` | (import 용) | 시연 이력 A~M2 · 고정 시계 — `demo-setting.py` 와 structure · concepts · whatif 가 같이 쓴다 |
| `draw_features.py` | `python3 demo/draw_features.py` | `features_graph.png` — 기능 시연 한 장 요약 그림 |
| `example.txt` · `script.txt` | `python3 main.py < demo/example.txt` | 기본 예시 / 전체 기능 시나리오 (시계 고정 안 함) |

기대 출력과 비교: `python3 main.py --fixed-clock < demo/features.txt | diff - demo/features.out` → 아무것도 안 나오면 일치.
