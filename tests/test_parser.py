import pytest

from textmidi import ScoreError, parse


def notes(score, track=0):
    return [(n.start, n.written, n.pitch) for n in score.tracks[track].notes]


def test_sticky_durations_carry_across_bars_and_rests():
    s = parse("track T\n| C4:h D4 | E4:q F4 r G4 |")
    assert notes(s) == [(0, 2, 60), (2, 2, 62), (4, 1, 64), (5, 1, 65), (7, 1, 67)]


def test_first_note_defaults_to_quarter():
    s = parse("track T\nC4 D4")
    assert notes(s) == [(0, 1, 60), (1, 1, 62)]


def test_chord():
    s = parse("track T\n[C4 E4 G4]:h A4")
    assert notes(s) == [(0, 2, 60), (0, 2, 64), (0, 2, 67), (2, 2, 69)]


def test_tie_across_bar_line():
    s = parse("track T\n| C4:w~ | C4:h r:h |")
    assert notes(s) == [(0, 6, 60)]
    assert not s.warnings


def test_partial_chord_tie():
    s = parse("track T\n| [C4~ E4 G4]:w | [C4 F4 A4]:w |")
    assert sorted(notes(s)) == [(0, 4, 64), (0, 4, 67), (0, 8, 60), (4, 4, 65), (4, 4, 69)]


def test_unresolved_tie_warns():
    s = parse("track T\n| C4:h~ D4:h |")
    assert notes(s) == [(0, 2, 60), (2, 2, 62)]
    assert "tie (~) on C4" in s.warnings[0].msg


def test_velocity_accent_and_dynamics():
    s = parse("track T  vel=80\nC4:q C4> C4!30 @ff C4 C4 @vel=100 C4 C4!120>")
    assert [n.vel for n in s.tracks[0].notes] == [80, 100, 30, 112, 112, 100, 127]


def test_repeats_nest():
    s = parse("track T\n( C4:e D4 ) x3 ( ( E4:s ) x2 F4:e ) x2")
    assert [n.pitch for n in s.tracks[0].notes] == [60, 62] * 3 + [64, 64, 65] * 2
    assert s.tracks[0].length == 3 + 2


def test_patterns():
    s = parse("define riff { | C4:q D4 E4 F4 | }\ntrack T\n$riff x2 $riff")
    assert len(s.tracks[0].notes) == 12
    assert s.bars == 3


def test_unknown_pattern_suggests():
    with pytest.raises(ScoreError, match="did you mean 'riff'"):
        parse("define riff { C4 }\ntrack T\n$rif")


def test_recursive_pattern_is_an_error():
    with pytest.raises(ScoreError, match="uses itself"):
        parse("define a { $a }\ntrack T\n$a")


def test_drums():
    s = parse("track D drums\n[kick hat]:e hat snare n42")
    assert [n.pitch for n in s.tracks[0].notes] == [36, 42, 42, 38, 42]
    assert s.tracks[0].channel == 9


def test_drum_name_in_melodic_track():
    with pytest.raises(ScoreError, match="drum names only work in tracks marked `drums`"):
        parse("track T\nkick")


def test_lowercase_pitch_hint():
    with pytest.raises(ScoreError, match="uppercase: 'C4'"):
        parse("track T\nc4")


def test_channels_skip_ten():
    text = "\n".join(f"track T{i}\nC4" for i in range(12)) + "\ntrack D drums\nkick"
    s = parse(text)
    assert [t.channel for t in s.tracks] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 9]


def test_too_many_melodic_tracks():
    with pytest.raises(ScoreError, match="more than 15"):
        parse("\n".join(f"track T{i}\nC4" for i in range(16)))


def test_header_and_tempo_changes():
    s = parse('title "Song"\ntempo 96\ntime 3/4\nkey F#m\ntrack T\n| C4:h. | @tempo=80 D4:h. |')
    assert s.title == "Song"
    assert s.key == "F#m"
    assert s.tempos == [(0, 96.0), (3, 80.0)]
    assert s.meters == [(0, 3, 4)]


def test_header_accepts_equals_form():
    s = parse("tempo=100\ntime: 6/8\ntrack T\nC4")
    assert s.tempos == [(0, 100.0)]
    assert s.meters == [(0, 6, 8)]


def test_header_keyword_inside_track_is_an_error():
    with pytest.raises(ScoreError, match="use @tempo="):
        parse("track T\nC4\ntempo 90")


def test_conflicting_tempo_marks():
    with pytest.raises(ScoreError, match="conflicting @tempo"):
        parse("track A\n@tempo=90 C4\ntrack B\n@tempo=100 C4")


def test_sustain_and_cc():
    s = parse("track T\n@sustain=on C4:w @sustain=off @cc74=100 @mod=20")
    c = [(x.pos, x.kind, x.number, x.value) for x in s.tracks[0].controls]
    assert c == [(0, "cc", 64, 127), (4, "cc", 64, 0), (4, "cc", 74, 100), (4, "cc", 1, 20)]


def test_ramp_steps_and_dedupes():
    s = parse("track T\n@expr=0..127:w C4:w")
    c = s.tracks[0].controls
    assert c[0].value == 0 and c[-1].value == 127
    assert c[0].pos == 0 and c[-1].pos == 4
    assert all(a.value < b.value and a.pos < b.pos for a, b in zip(c, c[1:]))
    assert len(c) == 65  # 16 steps per beat, plus the end point

    s = parse("track T\n@mod=0..2:w C4:w")
    assert [(x.pos, x.value) for x in s.tracks[0].controls] == [(0, 0), (1, 1), (3, 2)]


def test_ramp_does_not_move_the_cursor():
    s = parse("track T\n@expr=40..110:w C4:q D4")
    assert notes(s) == [(0, 1, 60), (1, 1, 62)]


def test_bend_scaling():
    s = parse("track T\n@bend=2 C4 @bend=-2 C4 @bend=1 C4 @bend=0 C4")
    assert [c.value for c in s.tracks[0].controls] == [8191, -8192, 4096, 0]
    s = parse("track T bendrange=12\n@bend=12 C4 @bend=-6 C4")
    assert [c.value for c in s.tracks[0].controls] == [8191, -4096]


def test_bend_beyond_range():
    with pytest.raises(ScoreError, match="bendrange"):
        parse("track T\n@bend=3 C4")


def test_ramp_needs_length():
    with pytest.raises(ScoreError, match="needs a length"):
        parse("track T\n@expr=0..100 C4")


def test_program_change_directive():
    s = parse("track T program=piano\nC4 @program=strings C4")
    assert s.tracks[0].program == 0
    assert [(c.kind, c.value) for c in s.tracks[0].controls] == [("program", 48)]


def test_unknown_things_are_reported_with_location():
    with pytest.raises(ScoreError) as e:
        parse("track T\n| C4:q D4 Q4 E4 |")
    issue = e.value.issues[0]
    assert (issue.line, issue.col) == (2, 11)
    assert "isn't a pitch" in issue.msg

    with pytest.raises(ScoreError, match="unknown directive '@expresion'.*did you mean"):
        parse("track T\n@expresion=3 C4")
    with pytest.raises(ScoreError, match="unknown track option"):
        parse("track T volume=3\nC4")
    with pytest.raises(ScoreError, match="bad duration"):
        parse("track T\nC4:x")


def test_chord_duration_inside_brackets_is_an_error():
    with pytest.raises(ScoreError, match="after the bracket"):
        parse("track T\n[C4:h E4]")


def test_music_before_first_track():
    with pytest.raises(ScoreError, match="before the first `track`"):
        parse("| C4 |")


def test_stray_repeat_count():
    with pytest.raises(ScoreError, match="right after"):
        parse("track T\nC4 x2")


def test_markdown_reply_is_unwrapped_and_lines_are_kept():
    reply = "Here is your song:\n\n```textmidi\ntrack T\n| C4:w |\n| D4:h |\n```\n\nEnjoy!"
    with pytest.raises(ScoreError) as e:
        parse(reply)
    assert e.value.issues[0].line == 6

    s = parse("Sure!\n```\ntrack T\nC4\n```\n")
    assert notes(s) == [(0, 1, 60)]


def test_textmidi_fence_is_preferred():
    reply = "```python\nprint('hi')\n```\n```textmidi\ntrack T\nC4\n```"
    assert notes(parse(reply)) == [(0, 1, 60)]


def test_comments_and_sharps():
    s = parse("# a comment\ntrack T  # another\nC#4 # trailing\nDb4")
    assert [n.pitch for n in s.tracks[0].notes] == [61, 61]
