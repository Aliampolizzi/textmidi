from fractions import Fraction

import pytest

from textmidi import tables


@pytest.mark.parametrize("text, expected", [
    ("A0", 21), ("C4", 60), ("A4", 69), ("B#3", 60), ("Cb4", 59), ("C8", 108),
    ("C-1", 0), ("G9", 127), ("F##2", 43), ("Ebb3", 50), ("n60", 60), ("n0", 0),
])
def test_parse_pitch(text, expected):
    assert tables.parse_pitch(text) == expected


@pytest.mark.parametrize("text", ["c4", "H4", "C", "C#", "4", "Cx4", "kick", ""])
def test_parse_pitch_rejects(text):
    assert tables.parse_pitch(text) is None


def test_pitch_name_round_trips():
    for n in range(128):
        assert tables.parse_pitch(tables.pitch_name(n)) == n


@pytest.mark.parametrize("text, beats", [
    ("w", 4), ("h", 2), ("q", 1), ("e", Fraction(1, 2)), ("s", Fraction(1, 4)), ("t", Fraction(1, 8)),
    ("q.", Fraction(3, 2)), ("h.", 3), ("q..", Fraction(7, 4)), ("e3", Fraction(1, 3)),
    ("q3", Fraction(2, 3)), ("s3", Fraction(1, 6)), ("1.5", Fraction(3, 2)), ("1/3", Fraction(1, 3)), ("3", 3),
])
def test_parse_duration(text, beats):
    assert tables.parse_duration(text) == beats


@pytest.mark.parametrize("text", ["x", "0", "0/1", "1/0", "q...", "-1", "qq", ""])
def test_parse_duration_rejects(text):
    assert tables.parse_duration(text) is None


def test_resolve_program():
    assert tables.resolve_program("piano") == 0
    assert tables.resolve_program("electric_bass_finger") == 33
    assert tables.resolve_program("Electric Bass (finger)") == 33
    assert tables.resolve_program("strings") == 48
    assert tables.resolve_program("gunshot") == 127
    assert tables.resolve_program("40") == 40
    with pytest.raises(ValueError, match="did you mean"):
        tables.resolve_program("violn")
    with pytest.raises(ValueError, match="out of range"):
        tables.resolve_program("128")


def test_drum_names():
    assert tables.drum_note("kick") == 36
    assert tables.drum_note("snare") == 38
    assert tables.drum_note("hat") == 42
    assert tables.drum_note("hat_open") == 46
    assert tables.drum_note("crash") == 49
    assert tables.drum_note("hh") == 42
    assert tables.drum_note("C4") is None


@pytest.mark.parametrize("text, key", [
    ("Am", "Am"), ("A minor", "Am"), ("Bb", "Bb"), ("F# major", "F#"), ("c#m", "C#m"), ("D#", None), ("H", None),
])
def test_parse_key(text, key):
    assert tables.parse_key(text) == key


def test_fmt_beats():
    assert tables.fmt_beats(Fraction(4)) == "4"
    assert tables.fmt_beats(Fraction(7, 2)) == "3.5"
    assert tables.fmt_beats(Fraction(1, 16)) == "0.0625"
    assert tables.fmt_beats(Fraction(10, 3)) == "10/3"
