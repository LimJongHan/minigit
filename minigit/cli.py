"""CLI 계층 — 한 줄 입력을 토큰으로 나누고(파싱), 명령을 고르고(디스패치), 출력 문자열을 만든다.

저장소(Repository) 는 값만 돌려주고, 사람이 읽는 문자열은 전부 여기서 만든다.
그래서 엔진은 테스트하기 쉽고, 출력 형식은 엔진을 건드리지 않고 바꿀 수 있다.
"""

import shlex
from datetime import datetime

from .diff import diff_lines, read_lines
from .repository import MiniGitError, Repository

PROMPT = "mini-git> "

HELP_TEXT = """\
Commands (case-insensitive, quote arguments that contain spaces):
  INIT <user_name>                 initialize repository / change current user
  BRANCH [<branch_name>]           create a branch at HEAD (no arg: list branches)
  SWITCH [--orphan] <branch_name>  move HEAD to a branch (--orphan: new root branch)
  COMMIT [--date="YYYY-MM-DD HH:MM:SS"] <message>
                                   commit on the current branch (--date: set the time)
  LOG [--sort-by=date|author] [--algo=merge|quick|heap|insertion]
  PATH <commit1> <commit2>         shortest undirected path between commits
  ANCESTORS <commit_hash>          all ancestors of a commit
                                   (<commit> may also be a branch name or HEAD)
  SEARCH <keyword>                 commits whose message contains the keyword(s)
  SEARCH --author=<name>           commits by an author
  MERGE <branch_name> [<message>]  create a merge commit with two parents
  DIFF <file1> <file2>             line-by-line diff of two text files
  HELP                             show this help
  # ...                            comment line (ignored)
  EXIT | QUIT                      leave"""


class ParseError(Exception):
    """따옴표가 안 닫히는 등 토큰 분리 단계의 오류."""


def tokenize(line):
    """공백 기준으로 나누되, 따옴표로 감싼 부분은 공백째 한 토큰으로 본다.

    shlex 는 셸과 같은 규칙으로 쪼갠다: `commit "Add signup"` → ['commit', 'Add signup'].
    따옴표가 안 닫히면 ValueError 를 내는데, 이를 ParseError 로 바꿔 'Invalid args' 로 보여준다.
    """
    try:
        return shlex.split(line)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc


def text_arg(args):
    """문자열 인자(사용자명/메시지/키워드). 따옴표를 빼먹어도 나머지 토큰을 이어 붙여 받아준다."""
    if not args:
        raise MiniGitError("Invalid args")
    return " ".join(args)


# ===================================================================== 출력 포맷
def fmt_commit_line(commit):
    return f"- {commit.hash}: {commit.message}"


def fmt_count(n):
    return f"{n} commit" if n == 1 else f"{n} commits"


def fmt_commit_list(commits, before, after):
    """머리말 = before + '1 commit' / '3 commits' + after, 그 아래 커밋 목록.

    사용자 입력(브랜치 이름 등)이 든 문자열을 '템플릿' 으로 해석하지 않고 이어 붙이기만 한다.
    format() 은 입력 속 중괄호(`a{b}`)에 KeyError 로 깨지고, replace("{count}") 도
    이름이 정확히 `{count}` 인 브랜치에서 그 글자까지 바꿔버린다.
    """
    lines = [before + fmt_count(len(commits)) + after]
    lines.extend(fmt_commit_line(c) for c in commits)
    return "\n".join(lines)


def fmt_log(repo, commits, show_labels=True):
    if not commits:
        return "No commits yet"
    blocks = []
    for c in commits:
        head = f"commit {c.hash} ({c.author}, {c.time_str()})"
        labels = repo.labels_for(c.hash) if show_labels else []
        if labels:
            head += f" [{', '.join(labels)}]"
        lines = [head]
        if len(c.parents) > 1:
            lines.append(f"Merge: {' '.join(c.parents)}")
        lines.append(f"    {c.message}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


# ===================================================================== 명령
class MiniGitCLI:
    """명령 한 줄 → 출력 문자열. REPL 루프(main.py) 와 테스트가 같은 진입점을 쓴다."""

    def __init__(self, repo=None):
        self.repo = repo or Repository()
        self.handlers = {
            "init": self.cmd_init,
            "branch": self.cmd_branch,
            "switch": self.cmd_switch,
            "commit": self.cmd_commit,
            "log": self.cmd_log,
            "path": self.cmd_path,
            "ancestors": self.cmd_ancestors,
            "search": self.cmd_search,
            "merge": self.cmd_merge,
            "diff": self.cmd_diff,
            "help": self.cmd_help,
        }

    def execute(self, line):
        """반환: (출력 문자열, 계속 실행할지). 빈 줄·`#` 주석 줄이면 ('', True)."""
        if line.lstrip().startswith("#"):
            return "", True  # 시연 스크립트에 설명을 적을 수 있게
        try:
            tokens = tokenize(line)
        except ParseError:
            return "Invalid args (unclosed quote)", True
        if not tokens:
            return "", True
        name, args = tokens[0].lower(), tokens[1:]
        if name in ("exit", "quit"):
            return "Bye.", False
        handler = self.handlers.get(name)
        if handler is None:
            return f"Unknown command: {tokens[0]}", True
        try:
            return handler(args), True
        except MiniGitError as exc:
            return str(exc), True

    # ------------------------------------------------------------------
    def cmd_init(self, args):
        repo = self.repo
        fresh = repo.init(text_arg(args))
        first = "Initialized repository." if fresh else "Reinitialized repository (history kept)."
        return f"{first}\nCurrent branch: {repo.head}\nCurrent user: {repo.user}"

    def cmd_branch(self, args):
        repo = self.repo
        if not args:
            repo._require_init()
            lines = []
            for name, target in repo.branches.items():
                marker = "*" if name == repo.head else " "
                lines.append(f"{marker} {name} {target or '(no commits)'}")
            return "\n".join(lines)
        if len(args) != 1:
            raise MiniGitError("Invalid args")
        repo.create_branch(args[0])
        return f"Created branch: {args[0]}"

    def cmd_switch(self, args):
        orphan = False
        if args and args[0].lower() == "--orphan":
            orphan, args = True, args[1:]
        if len(args) != 1:
            raise MiniGitError("Invalid args")
        changed = self.repo.switch(args[0], orphan=orphan)
        if orphan:
            return f"Switched to a new orphan branch: {args[0]}"
        if not changed:
            return f"Already on branch: {args[0]}"
        return f"Switched to branch: {args[0]}"

    def cmd_commit(self, args):
        """COMMIT [--date="YYYY-MM-DD HH:MM:SS"] <message>

        --date 는 `git commit --date` 처럼 커밋 시각을 직접 정한다. 시계가 틀린 컴퓨터에서
        만든 커밋(자식이 부모보다 '과거')을 재현해, LOG 가 시각이 아니라 관계로 정렬하는 이유를 보인다.
        """
        timestamp = None
        if args and args[0].lower().startswith("--date="):
            try:
                timestamp = datetime.strptime(args[0].partition("=")[2], "%Y-%m-%d %H:%M:%S")
            except ValueError as exc:
                raise MiniGitError("Invalid args") from exc
            args = args[1:]
        commit = self.repo.commit(text_arg(args), timestamp=timestamp)
        return f"[{self.repo.head} {commit.hash}] {commit.message}"

    def cmd_log(self, args):
        sort_by, algorithm = None, "merge"
        for arg in args:
            option, _, value = arg.partition("=")
            option, value = option.lower(), value.lower()
            if option == "--sort-by" and value in ("date", "author"):
                sort_by = value
            elif option == "--algo" and value:
                algorithm = value
            else:
                raise MiniGitError("Invalid args")
        commits = self.repo.log(sort_by=sort_by, algorithm=algorithm)
        # 정렬된 로그에서는 브랜치 표시가 그래프 위치와 무관해 보이므로 생략
        return fmt_log(self.repo, commits, show_labels=sort_by is None)

    def cmd_path(self, args):
        if len(args) != 2:
            raise MiniGitError("Invalid args")
        path = self.repo.path(args[0], args[1])
        if path is None:
            return "No path"
        steps = len(path) - 1
        return f"Path: {' -> '.join(path)} ({steps} {'edge' if steps == 1 else 'edges'})"

    def cmd_ancestors(self, args):
        if len(args) != 1:
            raise MiniGitError("Invalid args")
        found = self.repo.ancestors(args[0])
        return fmt_commit_list(found, f"Ancestors of {args[0]} (", "):")

    def cmd_search(self, args):
        query = text_arg(args)
        if query.lower().startswith("--author"):
            option, sep, name = query.partition("=")
            if option.lower() != "--author" or not sep or not name.strip():
                raise MiniGitError("Invalid args")
            return fmt_commit_list(self.repo.search_author(name), "Found ", ":")
        if query.startswith("--"):
            raise MiniGitError("Invalid args")
        return fmt_commit_list(self.repo.search_keyword(query), "Found ", ":")

    def cmd_merge(self, args):
        if not args:
            raise MiniGitError("Invalid args")
        message = " ".join(args[1:]) or None
        commit = self.repo.merge(args[0], message=message)
        if commit is None:
            return "Already up to date."
        return f"[{self.repo.head} {commit.hash}] {commit.message}\nMerge: {' '.join(commit.parents)}"

    def cmd_diff(self, args):
        if len(args) != 2:
            raise MiniGitError("Invalid args")
        try:
            a, b = read_lines(args[0]), read_lines(args[1])
        except FileNotFoundError as exc:
            raise MiniGitError(f"File not found: {exc.filename}") from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise MiniGitError(f"Cannot read file: {exc}") from exc
        rows = diff_lines(a, b)
        added = sum(1 for tag, _ in rows if tag == "+")
        removed = sum(1 for tag, _ in rows if tag == "-")
        lines = [f"--- {args[0]}", f"+++ {args[1]}"]
        lines.extend(f"{tag} {line}" for tag, line in rows)
        lines.append(f"({added} added, {removed} removed, {len(rows) - added - removed} unchanged)")
        return "\n".join(lines)

    def cmd_help(self, args):
        return HELP_TEXT
