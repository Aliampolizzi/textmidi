"""Data model shared by the parser, validator and writer.

Positions and durations are exact Fractions of a quarter note ("beats").
They only become MIDI ticks in the writer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class Issue:
    """An error or warning, with the source location when there is one."""

    msg: str
    line: int | None = None
    col: int | None = None

    def format(self, filename: str, kind: str) -> str:
        where = filename
        if self.line is not None:
            where += f":{self.line}"
            if self.col is not None:
                where += f":{self.col}"
        return f"{where}: {kind}: {self.msg}"


class ScoreError(Exception):
    """One or more problems that stop a score from converting."""

    def __init__(self, issues: str | list[Issue], line: int | None = None, col: int | None = None):
        if isinstance(issues, str):
            issues = [Issue(issues, line, col)]
        self.issues = list(issues)
        super().__init__("\n".join(i.format("line", "error") for i in self.issues))


@dataclass
class Note:
    start: Fraction
    written: Fraction  # notated length; ties add to it
    pitch: int
    vel: int
    gate: float  # fraction of `written` that sounds
    line: int
    col: int


@dataclass
class Control:
    pos: Fraction
    kind: str  # "cc", "bend" or "program"
    number: int  # controller number for "cc"; unused otherwise
    value: int  # 0-127, or -8192..8191 for "bend"


@dataclass
class Track:
    name: str
    line: int
    channel: int | None = None  # 0-based once assigned
    program: int | None = None
    drums: bool = False
    vel: int = 80
    gate: float = 1.0
    bendrange: float = 2.0
    humanize: bool = True
    notes: list[Note] = field(default_factory=list)
    controls: list[Control] = field(default_factory=list)
    barlines: list[tuple[Fraction, int, int]] = field(default_factory=list)  # (pos, line, col)
    length: Fraction = Fraction(0)


@dataclass
class Score:
    title: str | None = None
    key: str | None = None
    tempos: list[tuple[Fraction, float]] = field(default_factory=list)  # (pos, bpm), sorted
    meters: list[tuple[Fraction, int, int]] = field(default_factory=list)  # (pos, num, den), sorted
    tracks: list[Track] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    length: Fraction = Fraction(0)  # longest track
    bars: int = 0
