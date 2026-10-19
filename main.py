"""Mini Git 엔트리 포인트 — `python main.py` 로 REPL 을 시작한다.

REPL = Read(한 줄 읽기) → Eval(파싱·실행) → Print(출력) → Loop(반복).
`exit` / `quit`, Ctrl-D(EOF), Ctrl-C 로 종료한다.

파이프로 입력을 넣으면(`python main.py < demo/script.txt`) 입력 줄이 화면에 안 보이므로,
그때는 읽은 명령을 프롬프트 뒤에 다시 찍어 대화 기록처럼 보이게 한다.
`#` 주석 줄은 명령이 아니라 시연 설명이므로 프롬프트 없이 그대로 찍고, 빈 줄은 건너뛴다.

`python main.py --fixed-clock` 은 시계를 고정한다 — 기본 예시처럼 2025-03-10 09:00:00 부터
커밋마다 15분씩 흐른다. 시각이 hash 재료라서 hash 도 실행마다 같아지고,
시연 스크립트에 hash 를 그대로 적을 수 있다.
"""

import sys
from datetime import datetime, timedelta

from minigit import PROMPT, MiniGitCLI, Repository


class StepClock:
    """부를 때마다 step 만큼 흐르는 결정적 시계 (--fixed-clock)."""

    def __init__(self, start=datetime(2025, 3, 10, 9, 0, 0), step=timedelta(minutes=15)):
        self.now, self.step = start, step

    def __call__(self):
        current = self.now
        self.now += self.step
        return current


def repl(stdin=sys.stdin, stdout=sys.stdout, clock=None):
    cli = MiniGitCLI(Repository(clock=clock))
    interactive = stdin.isatty()
    while True:
        try:
            if interactive:
                line = input(PROMPT)
            else:
                line = stdin.readline()
                if not line:
                    raise EOFError
                line = line.rstrip("\n")
                if not line.strip():
                    continue  # 빈 줄은 건너뛴다 (출력 사이 빈 줄은 아래에서 따로 넣는다)
                if line.lstrip().startswith("#"):
                    print(line, file=stdout)  # 시연 설명은 프롬프트 없이 그대로
                    continue
                print(f"{PROMPT}{line}", file=stdout)
        except EOFError:
            if interactive:
                print(file=stdout)  # Ctrl-D 뒤 프롬프트 줄을 끝내준다
            break
        except KeyboardInterrupt:
            print("\nBye.", file=stdout)
            break
        output, keep_running = cli.execute(line)
        if output:
            print(output, file=stdout)
        if not keep_running:
            break
        if not interactive and output:
            print(file=stdout)


if __name__ == "__main__":
    repl(clock=StepClock() if "--fixed-clock" in sys.argv[1:] else None)
