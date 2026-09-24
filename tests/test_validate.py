import pytest

from textmidi import ScoreError, parse


def test_correct_bars_pass():
    s = parse("track T\n| C4:q D4 E4 F4 | G4:h. r:q | C4:e3 D4 E4 F4:q G4:h |")
    assert s.bars == 3
    assert not s.warnings


def test_short_bar_reports_bar_number_and_location():
    with pytest.raises(ScoreError) as e:
        parse("track Bass\n| C4:w |\n| D4:h. E4:e |")
    [issue] = e.value.issues
    assert issue.msg == "track 'Bass': bar 2 has 3.5 beats, but a 4/4 bar has 4"
    assert (issue.line, issue.col) == (3, 14)


def test_one_bad_bar_does_not_cascade():
    with pytest.raises(ScoreError) as e:
        parse("track T\n| C4:q. D4:q E4 F4 | C4:w | C4:w | C4:h C4:q | C4:w |")
    msgs = [i.msg for i in e.value.issues]
    assert msgs == [
        "track 'T': bar 1 has 4.5 beats, but a 4/4 bar has 4",
        "track 'T': bar 4 has 3 beats, but a 4/4 bar has 4",
    ]


def test_lenient_turns_bar_errors_into_warnings():
    s = parse("track T\n| C4:h |", lenient=True)
    assert "bar 1 has 2 beats" in s.warnings[0].msg


def test_double_bar_lines_and_repeats_that_wrap_bars():
    s = parse("track T\n( | C4:w | ) x3 || D4:w ||")
    assert s.bars == 4
    assert not s.warnings


def test_bar_lines_are_optional_but_must_land_on_bars():
    parse("track T\nC4:w D4:w | E4:w")
    with pytest.raises(ScoreError, match="bar 1 has 5 beats"):
        parse("track T\nC4:w D4:q | E4:w")


def test_six_eight_bar_is_three_quarter_beats():
    parse("time 6/8\ntrack T\n| A3:e C4 E4 A4 E4 C4 | G3:q. B3:q. |")
    with pytest.raises(ScoreError, match=r"a 6/8 bar has 3 \(beats are quarter notes\)"):
        parse("time 6/8\ntrack T\n| A3:e C4 E4 A4 E4 C4 A4 |")


def test_time_signature_change():
    s = parse("track T\n| C4:w | @time=3/4 C4:h. | C4:h. | @time=4/4 C4:w |")
    assert s.meters == [(0, 4, 4), (4, 3, 4), (10, 4, 4)]
    assert s.bars == 4


def test_time_change_inside_a_bar():
    with pytest.raises(ScoreError, match=r"@time=3/4 is 2 beats into bar 1"):
        parse("track T\n| C4:h @time=3/4 C4:h |")


def test_time_change_applies_to_every_track():
    parse("track A\n| C4:w | @time=3/4 C4:h. |\ntrack B\n| C4:w | C4:h. |")
    with pytest.raises(ScoreError, match="track 'B': bar 2 has 4 beats, but a 3/4 bar has 3"):
        parse("track A\n| C4:w | @time=3/4 C4:h. |\ntrack B\n| C4:w | C4:w |")


def test_track_length_mismatch_warns():
    s = parse("track Keys\n| C4:w | C4:w |\ntrack Bass\n| C2:w | C2:h")
    [w] = s.warnings
    assert w.msg == "track 'Bass' ends in bar 2 (beat 3), but 'Keys' ends after bar 2"


def test_error_list_is_capped():
    text = "track T\n" + "| C4:h " * 30 + "|"
    with pytest.raises(ScoreError) as e:
        parse(text)
    assert len(e.value.issues) == 11
    assert e.value.issues[-1].msg == "...and 20 more"
