"""Score text -> tokens, with `define` patterns and `( ... ) xN` repeats expanded."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import ScoreError
from .tables import suggest

_FENCE_RE = re.compile(r"\s*(```+|~~~+)\s*([\w-]*)")
_DELIMITERS = set('[](){}|"')
_PATTERN_NAME_RE = re.compile(r"[A-Za-z_]\w*")
_REPEAT_RE = re.compile(r"x(\d+)")
MAX_TOKENS = 1_000_000


@dataclass(frozen=True)
class Token:
    text: str
    line: int
    col: int
    quoted: bool = False

    def is_(self, text: str) -> bool:
        return self.text == text and not self.quoted


def extract_fenced(text: str) -> str:
    """Keep only the score if the text is a Markdown reply with code fences.

    Picks the first ```textmidi block, else the first fenced block. Other lines
    are blanked rather than dropped so error line numbers match the file.
    """
    lines = text.splitlines()
    blocks = []  # (info string, first content line, end line exclusive)
    i = 0
    while i < len(lines):
        m = _FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence, info = m.groups()
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith(fence[:3]):
            j += 1
        blocks.append((info.lower(), i + 1, j))
        i = j + 1
    if not blocks:
        return text
    _, start, end = next((b for b in blocks if b[0] == "textmidi"), blocks[0])
    return "\n".join(line if start <= k < end else "" for k, line in enumerate(lines))


def tokenize(text: str) -> list[Token]:
    """Split into tokens. `[ ( ) { } |` stand alone; `]` keeps its suffix (`]:h~`).

    `#` starts a comment only at the start of a token, so `C#4` is a pitch.
    """
    tokens = []
    for lineno, line in enumerate(text.splitlines(), 1):
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            if c.isspace():
                i += 1
                continue
            if c == "#":
                break
            col = i + 1
            if c == '"':
                end = line.find('"', i + 1)
                if end < 0:
                    raise ScoreError("unterminated string", lineno, col)
                tokens.append(Token(line[i + 1 : end], lineno, col, quoted=True))
                i = end + 1
                continue
            if c in "[(){}|":
                tokens.append(Token(c, lineno, col))
                i += 1
                continue
            j = i + 1 if c == "]" else i
            while j < n and not line[j].isspace() and line[j] not in _DELIMITERS:
                j += 1
            tokens.append(Token(line[i:j], lineno, col))
            i = j
    return tokens


def collect_defines(tokens: list[Token]) -> tuple[list[Token], dict[str, list[Token]]]:
    """Pull `define NAME { ... }` blocks out of the stream."""
    out: list[Token] = []
    patterns: dict[str, list[Token]] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if not t.is_("define"):
            if t.is_("{") or t.is_("}"):
                raise ScoreError("'{' and '}' only appear in `define NAME { ... }`", t.line, t.col)
            out.append(t)
            i += 1
            continue
        if i + 2 >= len(tokens) or not tokens[i + 2].is_("{"):
            raise ScoreError("expected `define NAME { ... }`", t.line, t.col)
        name = tokens[i + 1].text
        if not _PATTERN_NAME_RE.fullmatch(name):
            raise ScoreError(f"'{name}' isn't a valid pattern name (letters, digits, _)", t.line, t.col)
        if name in patterns:
            raise ScoreError(f"pattern '{name}' is defined twice", t.line, t.col)
        j = i + 3
        body = []
        while j < len(tokens) and not tokens[j].is_("}"):
            if tokens[j].is_("{") or tokens[j].is_("define"):
                raise ScoreError(f"pattern '{name}' is missing its closing '}}'", t.line, t.col)
            body.append(tokens[j])
            j += 1
        if j == len(tokens):
            raise ScoreError(f"pattern '{name}' is missing its closing '}}'", t.line, t.col)
        patterns[name] = body
        i = j + 1
    return out, patterns


def expand(tokens: list[Token], patterns: dict[str, list[Token]], _stack: tuple[str, ...] = ()) -> list[Token]:
    """Expand `$name`, `$name xN` and `( ... ) xN`, recursively."""
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.is_("("):
            depth, j = 1, i + 1
            while j < len(tokens) and depth:
                if tokens[j].is_("("):
                    depth += 1
                elif tokens[j].is_(")"):
                    depth -= 1
                j += 1
            if depth:
                raise ScoreError("'(' is never closed", t.line, t.col)
            body = expand(tokens[i + 1 : j - 1], patterns, _stack)
            count, i = _repeat_count(tokens, j)
        elif t.is_(")"):
            raise ScoreError("')' without a matching '('", t.line, t.col)
        elif t.text.startswith("$") and not t.quoted:
            name = t.text[1:]
            if name not in patterns:
                raise ScoreError(f"unknown pattern '${name}'" + suggest(name, patterns), t.line, t.col)
            if name in _stack:
                raise ScoreError(f"pattern '{name}' uses itself", t.line, t.col)
            body = expand(patterns[name], patterns, _stack + (name,))
            count, i = _repeat_count(tokens, i + 1)
        else:
            out.append(t)
            i += 1
            continue
        if len(out) + len(body) * count > MAX_TOKENS:
            raise ScoreError("score expands to more than a million tokens; check repeat counts", t.line, t.col)
        out.extend(body * count)
    return out


def _repeat_count(tokens: list[Token], i: int) -> tuple[int, int]:
    """Read an optional `xN` at tokens[i]; return (count, index after it)."""
    if i < len(tokens):
        m = _REPEAT_RE.fullmatch(tokens[i].text)
        if m and not tokens[i].quoted:
            count = int(m.group(1))
            if count < 1:
                raise ScoreError("repeat count must be at least 1", tokens[i].line, tokens[i].col)
            return count, i + 1
    return 1, i
