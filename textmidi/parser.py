"""Tokens -> Score: header lines, tracks, notes, chords, rests and @directives."""
from __future__ import annotations

import math
import re
from fractions import Fraction

from . import tables
from .lexer import Token, collect_defines, expand, extract_fenced, tokenize
from .model import Control, Issue, Note, Score, ScoreError, Track
from .validate import validate

_HEADER_KEYWORDS = ("title", "tempo", "time", "key")
_HEADER_INLINE_RE = re.compile(r"(title|tempo|time|key)[=:](.*)")
_NOTE_RE = re.compile(r"([^:~>!]*)(?::([^~>!]*))?(.*)")
_OPTION_RE = re.compile(r"([a-z_]+)=(\S+)")
_METER_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
_CC_RE = re.compile(r"cc(\d{1,3})")
_TRACK_OPTIONS = "program= channel= vel= gate= bendrange= humanize=off drums"
_DIRECTIVES = ["vel", "gate", "tempo", "time", "program", "sustain", "bend", *tables.CC_ALIASES]
_RAMP_STEPS_PER_BEAT = 16  # 30 ticks at 480 PPQ
_ACCENT = 20


def parse(text: str, *, lenient: bool = False) -> Score:
    """Parse and validate a score. Raises ScoreError; warnings land in score.warnings."""
    tokens = tokenize(extract_fenced(text))
    tokens, patterns = collect_defines(tokens)
    tokens = expand(tokens, patterns)
    return _Parser().run(tokens, lenient)


class _TrackState:
    """Sticky per-track values while its body is being read."""

    def __init__(self, track: Track):
        self.track = track
        self.pos = Fraction(0)
        self.dur = Fraction(1)
        self.vel = track.vel
        self.gate = track.gate
        self.ties: dict[int, Note] = {}


class _Parser:
    def __init__(self):
        self.score = Score()
        self.state: _TrackState | None = None
        self.header_tempo = 120.0
        self.header_meter = (4, 4)
        self.tempo_marks: list[tuple[Fraction, float, Token]] = []
        self.meter_marks: list[tuple[Fraction, tuple[int, int], Token]] = []

    # --- top level ---------------------------------------------------------

    def run(self, tokens: list[Token], lenient: bool) -> Score:
        i = 0
        while i < len(tokens):
            t = tokens[i]
            keyword, inline = self._header_keyword(t)
            if keyword:
                if self.state:
                    hint = f"; inside a track use @{keyword}=..." if keyword in ("tempo", "time") else ""
                    raise ScoreError(f"`{keyword}` belongs in the header, before the first track{hint}", t.line, t.col)
                args, i = self._rest_of_line(tokens, i)
                if inline:
                    args.insert(0, Token(inline, t.line, t.col + len(keyword) + 1))
                self._header(keyword, t, args)
            elif t.is_("track"):
                args, i = self._rest_of_line(tokens, i)
                self._start_track(t, args)
            elif self.state is None:
                raise ScoreError(f"'{t.text}' comes before the first `track` line", t.line, t.col)
            else:
                i = self._body(tokens, i)
        return self._finish(lenient)

    @staticmethod
    def _header_keyword(t: Token) -> tuple[str | None, str]:
        if t.quoted:
            return None, ""
        if t.text in _HEADER_KEYWORDS:
            return t.text, ""
        m = _HEADER_INLINE_RE.fullmatch(t.text)
        if m:
            return m.group(1), m.group(2)
        return None, ""

    @staticmethod
    def _rest_of_line(tokens: list[Token], i: int) -> tuple[list[Token], int]:
        line = tokens[i].line
        j = i + 1
        while j < len(tokens) and tokens[j].line == line:
            j += 1
        return list(tokens[i + 1 : j]), j

    def _header(self, keyword: str, t: Token, args: list[Token]) -> None:
        if not args:
            raise ScoreError(f"`{keyword}` needs a value", t.line, t.col)
        value = " ".join(a.text for a in args)
        if keyword == "title":
            self.score.title = value
        elif keyword == "tempo":
            self.header_tempo = self._tempo(value, args[0])
        elif keyword == "time":
            self.header_meter = self._meter(value, args[0])
        elif keyword == "key":
            key = tables.parse_key(value)
            if key is None:
                raise ScoreError(f"unknown key '{value}' (use e.g. C, F#, Bb, Am, C#m)", args[0].line, args[0].col)
            self.score.key = key

    def _start_track(self, t: Token, args: list[Token]) -> None:
        self._close_track()
        if not args or "=" in args[0].text:
            raise ScoreError("`track` needs a name: track NAME option=value ...", t.line, t.col)
        track = Track(name=args[0].text, line=t.line)
        for opt in args[1:]:
            if opt.is_("drums"):
                track.drums = True
                continue
            m = _OPTION_RE.fullmatch(opt.text)
            if not m or opt.quoted:
                raise ScoreError(
                    f"unknown track option '{opt.text}' (options: {_TRACK_OPTIONS});"
                    " the music goes on the lines after `track`",
                    opt.line, opt.col,
                )
            key, value = m.groups()
            if key == "program":
                track.program = self._program(value, opt)
            elif key == "channel":
                track.channel = self._int(value, opt, 1, 16, "channel") - 1
            elif key == "vel":
                track.vel = tables.DYNAMICS.get(value) or self._int(value, opt, 1, 127, "vel")
            elif key == "gate":
                track.gate = self._float(value, opt, 0, 2, "gate", low_open=True)
            elif key == "bendrange":
                track.bendrange = self._float(value, opt, 0, 24, "bendrange", low_open=True)
            elif key == "humanize":
                if value not in ("on", "off"):
                    raise ScoreError("use humanize=on or humanize=off", opt.line, opt.col)
                track.humanize = value == "on"
            else:
                raise ScoreError(
                    f"unknown track option '{key}'" + tables.suggest(key, _TRACK_OPTIONS.replace("=", "").split()),
                    opt.line, opt.col,
                )
        self.score.tracks.append(track)
        self.state = _TrackState(track)

    def _close_track(self) -> None:
        if self.state:
            self.state.track.length = self.state.pos
            self._drop_ties()

    # --- track body --------------------------------------------------------

    def _body(self, tokens: list[Token], i: int) -> int:
        t = tokens[i]
        s = self.state
        if t.quoted:
            raise ScoreError(f'unexpected string "{t.text}"', t.line, t.col)
        if t.text == "|":
            s.track.barlines.append((s.pos, t.line, t.col))
            return i + 1
        if t.text == "[":
            return self._chord(tokens, i)
        if t.text.startswith("]"):
            raise ScoreError("']' without a matching '['", t.line, t.col)
        if t.text.startswith("@"):
            self._directive(t)
            return i + 1
        head, dur_text, suffix = _NOTE_RE.fullmatch(t.text).groups()
        if head == "r":
            if suffix:
                raise ScoreError("rests can't take ~, > or !", t.line, t.col)
            dur = self._duration(dur_text, t)
            self._drop_ties()
            s.pos += dur
            return i + 1
        pitch = self._pitch(head, t)
        dur = self._duration(dur_text, t)
        tie, accent, vel = self._suffix(suffix, t)
        self._play([(pitch, tie)], dur, accent, vel, t)
        return i + 1

    def _chord(self, tokens: list[Token], i: int) -> int:
        opener = tokens[i]
        members: list[tuple[int, bool]] = []
        j = i + 1
        while j < len(tokens) and not tokens[j].text.startswith("]"):
            m = tokens[j]
            if m.quoted or m.text in ("[", "|") or m.text.startswith("@"):
                raise ScoreError("chords hold only pitches: [C4 E4 G4]:h", m.line, m.col)
            head, dur_text, suffix = _NOTE_RE.fullmatch(m.text).groups()
            if dur_text is not None:
                raise ScoreError("put the chord's duration after the bracket: [C4 E4 G4]:h", m.line, m.col)
            tie, accent, vel = self._suffix(suffix, m)
            if accent or vel is not None:
                raise ScoreError("put > or !NN after the closing bracket: [C4 E4]:q>", m.line, m.col)
            pitch = self._pitch(head, m)
            if all(p != pitch for p, _ in members):
                members.append((pitch, tie))
            j += 1
        if j == len(tokens):
            raise ScoreError("'[' is never closed", opener.line, opener.col)
        closer = tokens[j]
        if not members:
            raise ScoreError("empty chord", opener.line, opener.col)
        head, dur_text, suffix = _NOTE_RE.fullmatch(closer.text[1:]).groups()
        if head:
            raise ScoreError(f"unexpected '{head}' after ']' (expected ]:duration)", closer.line, closer.col)
        dur = self._duration(dur_text, closer)
        tie_all, accent, vel = self._suffix(suffix, closer)
        self._play([(p, tie or tie_all) for p, tie in members], dur, accent, vel, opener)
        return j + 1

    def _play(self, members: list[tuple[int, bool]], dur: Fraction, accent: bool, vel: int | None, t: Token) -> None:
        s = self.state
        velocity = vel if vel is not None else s.vel
        if accent:
            velocity += _ACCENT
        velocity = max(1, min(127, velocity))
        new_ties: dict[int, Note] = {}
        for pitch, tie in members:
            held = s.ties.pop(pitch, None)
            if held is not None and held.start + held.written == s.pos:
                held.written += dur
                note = held
            else:
                note = Note(s.pos, dur, pitch, velocity, s.gate, t.line, t.col)
                s.track.notes.append(note)
            if tie:
                new_ties[pitch] = note
        self._drop_ties()
        s.ties = new_ties
        s.pos += dur

    def _drop_ties(self) -> None:
        """Warn about ties that the next note didn't continue, then forget them."""
        for pitch, note in self.state.ties.items():
            name = str(pitch) if self.state.track.drums else tables.pitch_name(pitch)
            self.score.warnings.append(
                Issue(f"tie (~) on {name} isn't followed by the same pitch; it just ends", note.line, note.col)
            )
        self.state.ties = {}

    # --- @directives -------------------------------------------------------

    def _directive(self, t: Token) -> None:
        s = self.state
        body = t.text[1:]
        if body in tables.DYNAMICS:
            s.vel = tables.DYNAMICS[body]
            return
        if "=" not in body:
            hint = " (use @sustain=on or @sustain=off)" if body == "sustain" else tables.suggest(body, tables.DYNAMICS)
            raise ScoreError(f"unknown directive '{t.text}'{hint}", t.line, t.col)
        name, value = body.split("=", 1)
        if name == "vel":
            s.vel = tables.DYNAMICS.get(value) or self._int(value, t, 1, 127, "@vel")
        elif name == "gate":
            s.gate = self._float(value, t, 0, 2, "@gate", low_open=True)
        elif name == "tempo":
            self.tempo_marks.append((s.pos, self._tempo(value, t), t))
        elif name == "time":
            self.meter_marks.append((s.pos, self._meter(value, t), t))
        elif name == "program":
            s.track.controls.append(Control(s.pos, "program", 0, self._program(value, t)))
        elif name == "sustain":
            level = {"on": 127, "down": 127, "off": 0, "up": 0}.get(value)
            if level is None:
                level = self._int(value, t, 0, 127, "@sustain")
            s.track.controls.append(Control(s.pos, "cc", 64, level))
        elif name == "bend":
            rng = s.track.bendrange

            def to_bend(semitones: float) -> int:
                return max(-8192, min(8191, _round(semitones / rng * 8192)))

            self._automation(t, "bend", 0, value, -rng, rng, to_bend, f"±{rng:g} semitones (set bendrange= on the track)")
        elif name in tables.CC_ALIASES or _CC_RE.fullmatch(name):
            number = tables.CC_ALIASES.get(name)
            if number is None:
                number = int(_CC_RE.fullmatch(name).group(1))
                if number > 127:
                    raise ScoreError(f"controller {number} is out of range (0-127)", t.line, t.col)
            self._automation(t, "cc", number, value, 0, 127, _round, "0-127")
        else:
            raise ScoreError(f"unknown directive '@{name}'" + tables.suggest(name, _DIRECTIVES), t.line, t.col)

    def _automation(self, t: Token, kind: str, number: int, value: str, lo: float, hi: float, convert, range_text: str) -> None:
        """A single value (`@expr=90`) or a ramp (`@expr=40..110:w`) starting at the cursor."""
        s = self.state

        def number_in_range(text: str) -> float:
            try:
                v = float(text)
            except ValueError:
                raise ScoreError(f"'{text}' isn't a number in {t.text}", t.line, t.col) from None
            if not lo <= v <= hi:
                raise ScoreError(f"{text} is out of range in {t.text} ({range_text})", t.line, t.col)
            return v

        if ".." not in value:
            s.track.controls.append(Control(s.pos, kind, number, convert(number_in_range(value))))
            return
        start_text, rest = value.split("..", 1)
        if ":" not in rest:
            raise ScoreError(f"a ramp needs a length: {t.text}:w", t.line, t.col)
        end_text, length_text = rest.split(":", 1)
        a, b = number_in_range(start_text), number_in_range(end_text)
        length = tables.parse_duration(length_text)
        if length is None:
            raise ScoreError(f"bad ramp length ':{length_text}' in {t.text}", t.line, t.col)
        steps = max(1, math.ceil(length * _RAMP_STEPS_PER_BEAT))
        last = None
        for k in range(steps + 1):
            v = convert(a + (b - a) * k / steps)
            if v != last:
                s.track.controls.append(Control(s.pos + length * k / steps, kind, number, v))
                last = v

    # --- value helpers -----------------------------------------------------

    def _pitch(self, head: str, t: Token) -> int:
        drums = self.state.track.drums
        if drums:
            n = tables.drum_note(head)
            if n is not None:
                return n
        n = tables.parse_pitch(head)
        if n is None:
            if head == "":
                raise ScoreError(f"missing pitch in '{t.text}'", t.line, t.col)
            if re.fullmatch(r"x\d+", head):
                raise ScoreError(f"'{head}' must come right after ')' or a $pattern", t.line, t.col)
            if drums:
                raise ScoreError(
                    f"unknown drum '{head}'" + tables.suggest(head, [*tables.DRUMS, *tables.DRUM_ALIASES]), t.line, t.col
                )
            if tables.drum_note(head) is not None:
                raise ScoreError(f"'{head}' is a drum; drum names only work in tracks marked `drums`", t.line, t.col)
            if tables.parse_pitch(head[:1].upper() + head[1:]) is not None:
                raise ScoreError(f"note letters are uppercase: '{head[:1].upper() + head[1:]}'", t.line, t.col)
            raise ScoreError(f"'{head}' isn't a pitch (pitches look like C4, F#3, Bb2)", t.line, t.col)
        if not 0 <= n <= 127:
            raise ScoreError(f"'{head}' is outside the MIDI range (C-1 to G9)", t.line, t.col)
        return n

    def _duration(self, text: str | None, t: Token) -> Fraction:
        if text is None:
            return self.state.dur
        d = tables.parse_duration(text)
        if d is None:
            raise ScoreError(
                f"bad duration ':{text}' (use w h q e s t, with . or .. for dots and 3 for triplets, or beats like 1.5)",
                t.line, t.col,
            )
        self.state.dur = d
        return d

    @staticmethod
    def _suffix(text: str, t: Token) -> tuple[bool, bool, int | None]:
        tie = accent = False
        vel = None
        i = 0
        while i < len(text):
            if text[i] == "~":
                tie = True
                i += 1
            elif text[i] == ">":
                accent = True
                i += 1
            elif text[i] == "!":
                m = re.match(r"!(\d{1,3})", text[i:])
                if not m or not 1 <= int(m.group(1)) <= 127:
                    raise ScoreError(f"'!' needs a velocity 1-127, e.g. snare:s!35 (in '{t.text}')", t.line, t.col)
                vel = int(m.group(1))
                i += len(m.group(0))
            else:
                raise ScoreError(f"unexpected '{text[i:]}' in '{t.text}' (after the duration use ~ > or !NN)", t.line, t.col)
        return tie, accent, vel

    @staticmethod
    def _program(value: str, t: Token) -> int:
        try:
            return tables.resolve_program(value)
        except ValueError as e:
            raise ScoreError(str(e), t.line, t.col) from None

    @staticmethod
    def _tempo(value: str, t: Token) -> float:
        return _Parser._float(value, t, 0, 1000, "tempo", low_open=True)

    @staticmethod
    def _meter(value: str, t: Token) -> tuple[int, int]:
        m = _METER_RE.fullmatch(value)
        if not m:
            raise ScoreError(f"time signature '{value}' should look like 4/4 or 6/8", t.line, t.col)
        num, den = int(m.group(1)), int(m.group(2))
        if num < 1 or den not in (1, 2, 4, 8, 16, 32):
            raise ScoreError(f"unsupported time signature {value}", t.line, t.col)
        return num, den

    @staticmethod
    def _int(value: str, t: Token, lo: int, hi: int, what: str) -> int:
        if not value.isdigit() or not lo <= int(value) <= hi:
            raise ScoreError(f"{what} must be a whole number {lo}-{hi}, not '{value}'", t.line, t.col)
        return int(value)

    @staticmethod
    def _float(value: str, t: Token, lo: float, hi: float, what: str, low_open: bool = False) -> float:
        try:
            v = float(value)
        except ValueError:
            v = math.nan
        if not (lo < v <= hi if low_open else lo <= v <= hi):
            raise ScoreError(f"{what} must be a number between {lo:g} and {hi:g}, not '{value}'", t.line, t.col)
        return v

    # --- finishing ---------------------------------------------------------

    def _finish(self, lenient: bool) -> Score:
        self._close_track()
        score = self.score
        if not score.tracks:
            raise ScoreError("the score has no tracks (start one with `track NAME`)")
        score.tempos = _merge_marks(self.header_tempo, self.tempo_marks, "tempo")
        meters = _merge_marks(self.header_meter, self.meter_marks, "time")
        score.meters = [(pos, n, d) for pos, (n, d) in meters]
        meter_locations = {pos: (t.line, t.col) for pos, _, t in self.meter_marks}
        score.length = max(t.length for t in score.tracks)
        _assign_channels(score)
        validate(score, meter_locations, lenient)
        return score


def _round(x: float) -> int:
    """Round half up, so ramps step evenly (built-in round() rounds half to even)."""
    return math.floor(x + 0.5)


def _merge_marks(header_value, marks: list[tuple[Fraction, object, Token]], what: str) -> list[tuple[Fraction, object]]:
    """Combine the header value (at 0) with @tempo/@time marks from all tracks."""
    by_pos: dict[Fraction, tuple[object, Token | None]] = {Fraction(0): (header_value, None)}
    for pos, value, t in marks:
        if pos in by_pos:
            other_value, other = by_pos[pos]
            if other is not None and other_value != value:
                raise ScoreError(f"conflicting @{what} at the same point (another track set it on line {other.line})", t.line, t.col)
        by_pos[pos] = (value, t)
    return sorted((pos, value) for pos, (value, _) in by_pos.items())


def _assign_channels(score: Score) -> None:
    used = {t.channel for t in score.tracks if t.channel is not None}
    free = [c for c in range(16) if c != 9 and c not in used]
    for t in score.tracks:
        if t.channel is not None:
            continue
        if t.drums:
            t.channel = 9
        elif free:
            t.channel = free.pop(0)
        else:
            raise ScoreError(
                "more than 15 melodic tracks; give some of them the same channel= to share", t.line
            )
    programs: dict[int, tuple[int | None, str]] = {}
    for t in score.tracks:
        if t.channel in programs and programs[t.channel][0] != t.program:
            score.warnings.append(
                Issue(f"tracks '{programs[t.channel][1]}' and '{t.name}' share channel {t.channel + 1}"
                      " but ask for different programs", t.line)
            )
        programs.setdefault(t.channel, (t.program, t.name))
