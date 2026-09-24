"""Score -> Type-1 MIDI file: a conductor track plus one track per score track."""
from __future__ import annotations

import itertools
import random
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

import mido

from .model import Score, Track

PPQ = 480

# Events at the same tick go in this order, so a repeated note is released
# before it is struck again and a pedal change lands between the two.
_NOTE_OFF, _CONTROL, _NOTE_ON = 0, 1, 2


@dataclass
class Humanize:
    timing: float = 6.0  # std-dev in ticks (480 per beat), clipped at 2 sigma
    velocity: float = 5.0  # std-dev in velocity steps
    seed: int | None = None


def ticks(pos: Fraction) -> int:
    return round(pos * PPQ)


def build_midi(score: Score, humanize: Humanize | None = None) -> mido.MidiFile:
    rng = random.Random(humanize.seed) if humanize else None
    end = ticks(score.length)
    track_events = []
    for track in score.tracks:
        notes = [_sounding(n) for n in track.notes]
        if rng and track.humanize:
            notes = _humanize(notes, rng, humanize)
        events = _track_events(track, _tidy(notes))
        if events:
            end = max(end, events[-1][0])
        track_events.append(events)

    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ)
    mid.tracks.append(_to_track(score.title, _conductor_events(score), end))
    for track, events in zip(score.tracks, track_events):
        mid.tracks.append(_to_track(track.name, events, end))
    return mid


def _sounding(note) -> list[int]:
    """[start, end, pitch, velocity] in ticks, with the gate applied."""
    start = ticks(note.start)
    length = max(1, round(note.written * PPQ * note.gate))
    return [start, start + length, note.pitch, note.vel]


def _clipped_gauss(rng: random.Random, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return max(-2 * sigma, min(2 * sigma, rng.gauss(0, sigma)))


def _humanize(notes: list[list[int]], rng: random.Random, h: Humanize) -> list[list[int]]:
    out = []
    for start, end, pitch, vel in notes:
        shift = round(_clipped_gauss(rng, h.timing))
        new_start = max(0, start + shift)
        new_end = max(new_start + 1, end + shift)
        new_vel = max(1, min(127, vel + round(_clipped_gauss(rng, h.velocity))))
        out.append([new_start, new_end, pitch, new_vel])
    return out


def _tidy(notes: list[list[int]]) -> list[list[int]]:
    """Merge same-pitch notes that start together and cut a note short where the
    next note of the same pitch begins, so no note-off kills a later note."""
    by_pitch = defaultdict(list)
    for n in notes:
        by_pitch[n[2]].append(n)
    out = []
    for group in by_pitch.values():
        group.sort()
        kept: list[list[int]] = []
        for n in group:
            if kept and kept[-1][0] == n[0]:
                kept[-1][1] = max(kept[-1][1], n[1])
                kept[-1][3] = max(kept[-1][3], n[3])
                continue
            if kept and kept[-1][1] > n[0]:
                kept[-1][1] = n[0]
            kept.append(n)
        out.extend(kept)
    return out


def _track_events(track: Track, notes: list[list[int]]) -> list[tuple[int, int, int, mido.Message]]:
    """(tick, class, sequence, message), sorted."""
    ch = track.channel
    seq = itertools.count()
    events = []

    def add(tick: int, cls: int, msg: mido.Message) -> None:
        events.append((tick, cls, next(seq), msg))

    if track.program is not None:
        add(0, _CONTROL, mido.Message("program_change", channel=ch, program=track.program))
    if track.bendrange != 2:
        semitones = int(track.bendrange)
        cents = min(99, round((track.bendrange - semitones) * 100))
        # RPN 0 (pitch-bend sensitivity), then the null RPN so later CC6s are harmless.
        for control, value in ((101, 0), (100, 0), (6, semitones), (38, cents), (101, 127), (100, 127)):
            add(0, _CONTROL, mido.Message("control_change", channel=ch, control=control, value=value))
    for c in track.controls:
        if c.kind == "cc":
            msg = mido.Message("control_change", channel=ch, control=c.number, value=c.value)
        elif c.kind == "bend":
            msg = mido.Message("pitchwheel", channel=ch, pitch=c.value)
        else:
            msg = mido.Message("program_change", channel=ch, program=c.value)
        add(ticks(c.pos), _CONTROL, msg)
    for start, end, pitch, vel in notes:
        add(start, _NOTE_ON, mido.Message("note_on", channel=ch, note=pitch, velocity=vel))
        add(end, _NOTE_OFF, mido.Message("note_off", channel=ch, note=pitch, velocity=0))
    events.sort(key=lambda e: e[:3])
    return events


def _conductor_events(score: Score) -> list[tuple[int, int, int, mido.MetaMessage]]:
    seq = itertools.count()
    events = []
    for pos, num, den in score.meters:
        events.append((ticks(pos), 0, next(seq), mido.MetaMessage("time_signature", numerator=num, denominator=den)))
    if score.key:
        events.append((0, 0, next(seq), mido.MetaMessage("key_signature", key=score.key)))
    for pos, bpm in score.tempos:
        events.append((ticks(pos), 0, next(seq), mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))))
    events.sort(key=lambda e: e[:3])
    return events


def _to_track(name: str | None, events, end: int) -> mido.MidiTrack:
    track = mido.MidiTrack()
    if name:
        # MIDI text is Latin-1; replace anything it can't hold.
        track.append(mido.MetaMessage("track_name", name=name.encode("latin-1", "replace").decode("latin-1")))
    now = 0
    for tick, _, _, msg in events:
        track.append(msg.copy(time=tick - now))
        now = tick
    track.append(mido.MetaMessage("end_of_track", time=max(0, end - now)))
    return track
