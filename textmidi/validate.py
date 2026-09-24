"""Bar-line checks against the song's time signatures, plus track-length warnings."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from fractions import Fraction

from .model import Issue, Score, ScoreError, Track
from .tables import fmt_beats

MAX_ERRORS = 10


class Bars:
    """Where every bar starts, derived from the (pos, num, den) time-signature list."""

    def __init__(self, meters: list[tuple[Fraction, int, int]], end: Fraction,
                 locations: dict[Fraction, tuple[int, int]], errors: list[Issue]):
        self.starts: list[Fraction] = []
        self.sigs: list[tuple[int, int]] = []
        pending = list(meters[1:])
        sig = meters[0][1:]
        pos = Fraction(0)
        extra = 2  # a couple of bars past the end, so late bar lines can be located
        while True:
            while pending and pending[0][0] <= pos:
                change_pos, num, den = pending.pop(0)
                if change_pos < pos:
                    into = fmt_beats(change_pos - self.starts[-1])
                    errors.append(Issue(
                        f"@time={num}/{den} is {into} beats into bar {len(self.starts)};"
                        " time changes must sit on a bar line",
                        *locations.get(change_pos, (None, None)),
                    ))
                sig = (num, den)
            self.starts.append(pos)
            self.sigs.append(sig)
            if pos >= end:
                extra -= 1
                if extra < 0:
                    break
            pos += bar_length(*sig)
        self._start_set = set(self.starts)

    def index(self, pos: Fraction) -> int:
        """0-based index of the bar containing pos."""
        return bisect_right(self.starts, pos) - 1

    def is_start(self, pos: Fraction) -> bool:
        return pos in self._start_set

    def length(self, i: int) -> Fraction:
        return bar_length(*self.sigs[i])

    def count(self, end: Fraction) -> int:
        i = self.index(end)
        return i if self.starts[i] == end else i + 1

    def where_end(self, pos: Fraction) -> str:
        i = self.index(pos)
        if self.starts[i] == pos:
            return f"after bar {i}" if i else "at the very start"
        return f"in bar {i + 1} (beat {fmt_beats(pos - self.starts[i] + 1)})"

    def nearest_start_after(self, prev: Fraction, q: Fraction) -> Fraction:
        """The bar start after `prev` closest to `q` (earlier one on a tie)."""
        lo = bisect_right(self.starts, prev)
        j = bisect_left(self.starts, q)
        candidates = [self.starts[k] for k in (j - 1, j) if lo <= k < len(self.starts)]
        if not candidates:
            return self.starts[min(lo, len(self.starts) - 1)]
        return min(candidates, key=lambda s: (abs(s - q), s))


def bar_length(num: int, den: int) -> Fraction:
    return Fraction(4 * num, den)


def check_barlines(track: Track, bars: Bars) -> list[Issue]:
    """Every `|` must land on a bar start. After a miss, re-sync so one bad bar
    doesn't make every later bar line in the track fail too."""
    issues = []
    shift = Fraction(0)
    prev = Fraction(0)
    for pos, line, col in track.barlines:
        q = pos - shift
        if q == prev:
            continue
        if bars.is_start(q):
            prev = q
            continue
        i = bars.index(prev)
        need, seg = bars.length(i), q - prev
        num, den = bars.sigs[i]
        if seg < 2 * need:
            unit = "" if den == 4 else " (beats are quarter notes)"
            msg = (f"track '{track.name}': bar {i + 1} has {fmt_beats(seg)} beats, "
                   f"but a {num}/{den} bar has {fmt_beats(need)}{unit}")
        else:
            j = bars.index(q)
            msg = (f"track '{track.name}': bar line lands {fmt_beats(q - bars.starts[j])} beats into bar {j + 1} "
                   f"({fmt_beats(seg)} beats since the previous bar line)")
        issues.append(Issue(msg, line, col))
        target = bars.nearest_start_after(prev, q)
        shift += q - target
        prev = target
    return issues


def validate(score: Score, meter_locations: dict[Fraction, tuple[int, int]], lenient: bool) -> None:
    """Raise ScoreError for bad bars (warnings instead when lenient); fill score.bars."""
    errors: list[Issue] = []
    bars = Bars(score.meters, score.length, meter_locations, errors)
    bar_issues = [issue for track in score.tracks for issue in check_barlines(track, bars)]
    if lenient:
        score.warnings.extend(bar_issues)
    else:
        errors.extend(bar_issues)
    if errors:
        shown = errors[:MAX_ERRORS]
        if len(errors) > MAX_ERRORS:
            shown.append(Issue(f"...and {len(errors) - MAX_ERRORS} more"))
        raise ScoreError(shown)

    score.bars = bars.count(score.length)
    longest = max(score.tracks, key=lambda t: t.length)
    for t in score.tracks:
        if not t.notes:
            score.warnings.append(Issue(f"track '{t.name}' has no notes", t.line))
        elif t.length != longest.length:
            score.warnings.append(Issue(
                f"track '{t.name}' ends {bars.where_end(t.length)}, "
                f"but '{longest.name}' ends {bars.where_end(longest.length)}",
                t.line,
            ))
