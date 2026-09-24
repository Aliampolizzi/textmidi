import pytest

pytest.importorskip("tkinter")

from textmidi.gui import convert  # noqa: E402


def test_writes_mid_and_reports_summary(tmp_path):
    src = tmp_path / "song.txt"
    src.write_text("track Lead program=flute\n| C5:q D5 E5 F5 |", encoding="utf-8")
    ok, text = convert(str(src))
    assert ok
    assert (tmp_path / "song.mid").exists()
    assert "1 bar, 0:02, 1 track" in text


def test_reports_errors(tmp_path):
    src = tmp_path / "bad.txt"
    src.write_text("track T\n| C4:h |", encoding="utf-8")
    ok, text = convert(str(src))
    assert not ok
    assert text.startswith("bad.txt:2:8: error: track 'T': bar 1 has 2 beats")
    assert not (tmp_path / "bad.mid").exists()


def test_missing_file(tmp_path):
    ok, text = convert(str(tmp_path / "nope.txt"))
    assert not ok
    assert "Can't find" in text
