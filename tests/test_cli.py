import mido

from textmidi.__main__ import main


def test_writes_mid_next_to_input(tmp_path, capsys):
    src = tmp_path / "song.txt"
    src.write_text("track Lead program=flute\n| C5:q D5 E5 F5 |", encoding="utf-8")
    assert main([str(src)]) == 0
    assert mido.MidiFile(tmp_path / "song.mid").length > 0
    assert "1 bar, 0:02, 1 track" in capsys.readouterr().out


def test_errors_exit_1_with_location(tmp_path, capsys):
    src = tmp_path / "bad.txt"
    src.write_text("track T\n| C4:h |", encoding="utf-8")
    assert main([str(src)]) == 1
    assert f"{src}:2:8: error: track 'T': bar 1 has 2 beats" in capsys.readouterr().err
    assert not (tmp_path / "bad.mid").exists()


def test_reads_utf16_and_bom(tmp_path):
    for encoding in ("utf-16", "utf-8-sig"):
        src = tmp_path / f"{encoding}.txt"
        src.write_text("```textmidi\ntrack T\nC4\n```", encoding=encoding)
        assert main([str(src), "--check"]) == 0


def test_humanize_prints_seed(tmp_path, capsys):
    src = tmp_path / "song.txt"
    src.write_text("track T\n( C4:e D4 ) x4", encoding="utf-8")
    assert main([str(src), "--humanize", "--seed", "5"]) == 0
    assert "seed 5" in capsys.readouterr().out


def test_refuses_to_overwrite_input(tmp_path):
    src = tmp_path / "song.mid"
    src.write_text("track T\nC4", encoding="utf-8")
    assert main([str(src)]) == 2
