import io
from collections import defaultdict

import mido

from textmidi import Humanize, build_midi, convert, parse

SONG = """
title "Test Song"
tempo 96
time 4/4
key Am
track Keys  program=electric_piano_1  gate=0.5
| @sustain=on [A3 C4 E4]:h @sustain=off @sustain=on [F3 A3 C4]:h |
track Bass  program=bass
| A1:q A1 A1 A1 |
track Drums  drums
| [kick hat]:e hat [snare hat] hat [kick hat] hat [snare hat] hat |
"""


def absolute(track):
    t = 0
    for m in track:
        t += m.time
        yield t, m


def round_trip(mid):
    buf = io.BytesIO()
    mid.save(file=buf)
    buf.seek(0)
    return mido.MidiFile(file=buf)


def test_file_structure():
    mid = round_trip(convert(SONG))
    assert mid.type == 1 and mid.ticks_per_beat == 480
    assert len(mid.tracks) == 4
    conductor = {m.type: m for m in mid.tracks[0]}
    assert conductor["track_name"].name == "Test Song"
    assert conductor["set_tempo"].tempo == mido.bpm2tempo(96)
    assert (conductor["time_signature"].numerator, conductor["time_signature"].denominator) == (4, 4)
    assert conductor["key_signature"].key == "Am"
    names = [next(m.name for m in tr if m.type == "track_name") for tr in mid.tracks[1:]]
    assert names == ["Keys", "Bass", "Drums"]
    programs = [[m.program for m in tr if m.type == "program_change"] for tr in mid.tracks[1:]]
    assert programs == [[4], [33], []]
    assert {m.channel for m in mid.tracks[3] if m.type == "note_on"} == {9}
    assert sum(m.type == "note_on" for tr in mid.tracks for m in tr) == 6 + 4 + 12


def test_every_track_ends_at_song_end():
    mid = convert(SONG)
    for tr in mid.tracks:
        end_tick, last = list(absolute(tr))[-1]
        assert last.type == "end_of_track" and end_tick == 4 * 480


def test_repeated_note_releases_before_restriking():
    mid = convert("track T\nC4:q C4")
    events = [(t, m.type) for t, m in absolute(mid.tracks[1]) if m.type.startswith("note")]
    assert events == [(0, "note_on"), (480, "note_off"), (480, "note_on"), (960, "note_off")]


def test_pedal_change_sits_between_release_and_strike():
    mid = convert(SONG)
    at_960 = [m for t, m in absolute(mid.tracks[1]) if t == 960 and not m.is_meta]
    kinds = [m.type if m.type != "control_change" else f"cc64={m.value}" for m in at_960]
    assert kinds == ["cc64=0", "cc64=127", "note_on", "note_on", "note_on"]


def test_gate_shortens_notes():
    mid = convert(SONG)
    first_off = next(t for t, m in absolute(mid.tracks[1]) if m.type == "note_off")
    assert first_off == 480  # a half note at gate 0.5


def test_bendrange_emits_rpn_only_when_changed():
    ccs = lambda text: [(m.control, m.value) for m in convert(text).tracks[1] if m.type == "control_change"]
    assert ccs("track T\nC4") == []
    assert ccs("track T bendrange=12\nC4") == [(101, 0), (100, 0), (6, 12), (38, 0), (101, 127), (100, 127)]


def test_pitchwheel_values():
    mid = convert("track T\n@bend=2 C4 @bend=-2 C4")
    assert [m.pitch for m in mid.tracks[1] if m.type == "pitchwheel"] == [8191, -8192]


def test_overlapping_same_pitch_is_trimmed():
    mid = convert("track T gate=1.5\nC4:q C4 D4")
    assert_no_same_pitch_overlap(mid)


def assert_no_same_pitch_overlap(mid):
    for tr in mid.tracks[1:]:
        sounding = defaultdict(int)
        for t, m in absolute(tr):
            if m.type == "note_on" and m.velocity > 0:
                assert sounding[(m.channel, m.note)] == 0, f"overlap at tick {t}"
                sounding[(m.channel, m.note)] += 1
            elif m.type == "note_off":
                sounding[(m.channel, m.note)] -= 1


def as_bytes(mid):
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def test_humanize_is_repeatable():
    score = parse(SONG)
    a = as_bytes(build_midi(score, Humanize(timing=20, velocity=10, seed=7)))
    b = as_bytes(build_midi(score, Humanize(timing=20, velocity=10, seed=7)))
    c = as_bytes(build_midi(score, Humanize(timing=20, velocity=10, seed=8)))
    assert a == b
    assert a != c
    assert a != as_bytes(build_midi(score))


def test_humanize_never_overlaps_or_goes_negative():
    text = "track T\n( C4:t C4 D4 D4 [E4 G4] [E4 G4] C4 C4 ) x16"
    mid = build_midi(parse(text), Humanize(timing=30, velocity=40, seed=1))
    assert_no_same_pitch_overlap(mid)
    for t, m in absolute(mid.tracks[1]):
        assert t >= 0
        if m.type == "note_on":
            assert 1 <= m.velocity <= 127


def test_humanize_off_track_is_untouched():
    score = parse("track A humanize=off\n( C4:e D4 ) x8\ntrack B\n( C4:e D4 ) x8")
    plain = build_midi(score)
    loose = build_midi(score, Humanize(seed=3))
    assert list(plain.tracks[1]) == list(loose.tracks[1])
    assert list(plain.tracks[2]) != list(loose.tracks[2])
