"""Command line: py -m textmidi song.txt [-o song.mid] [--humanize] ..."""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from . import tables
from .model import Score, ScoreError
from .parser import parse
from .writer import Humanize, build_midi


def read_source(path: str) -> str:
    """Read a score, coping with the UTF-8 BOM / UTF-16 files Windows tools write."""
    data = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # not the StringIO the GUI captures output in
            stream.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="textmidi", description="Convert a textmidi score into a .mid file.")
    ap.add_argument("input", help="score file (a Markdown reply with a ```textmidi block also works), or - for stdin")
    ap.add_argument("-o", "--output", help="output path (default: the input name with .mid)")
    ap.add_argument("--check", action="store_true", help="validate and summarise without writing a file")
    ap.add_argument("--lenient", action="store_true", help="report bars with the wrong length as warnings, not errors")
    ap.add_argument("--humanize", action="store_true", help="add small random timing and velocity variation")
    ap.add_argument("--timing-jitter", type=float, default=6.0, metavar="TICKS",
                    help="humanize timing spread, std-dev in ticks at 480 per beat (default 6)")
    ap.add_argument("--vel-jitter", type=float, default=5.0, metavar="N",
                    help="humanize velocity spread, std-dev (default 5)")
    ap.add_argument("--seed", type=int, help="random seed for --humanize (default: random, and printed)")
    args = ap.parse_args(argv)

    name = "<stdin>" if args.input == "-" else args.input
    out = None
    if not args.check:
        if args.output:
            out = Path(args.output)
        elif args.input != "-":
            out = Path(args.input).with_suffix(".mid")
        else:
            print("textmidi: reading from stdin needs -o OUT.mid", file=sys.stderr)
            return 2
        if args.input != "-" and out.resolve() == Path(args.input).resolve():
            print("textmidi: the output would overwrite the input; pass -o", file=sys.stderr)
            return 2

    try:
        text = read_source(args.input)
    except (OSError, UnicodeDecodeError) as e:
        print(f"textmidi: can't read {name}: {e}", file=sys.stderr)
        return 2

    try:
        score = parse(text, lenient=args.lenient)
    except ScoreError as e:
        for issue in e.issues:
            print(issue.format(name, "error"), file=sys.stderr)
        return 1
    for w in score.warnings:
        print(w.format(name, "warning"), file=sys.stderr)

    humanize = None
    if args.humanize:
        seed = args.seed if args.seed is not None else random.randrange(1_000_000)
        humanize = Humanize(args.timing_jitter, args.vel_jitter, seed)
    mid = build_midi(score, humanize)
    if out:
        mid.save(out)
    print(summary(score, mid.length, out))
    if humanize:
        print(f"humanize seed {humanize.seed} (pass --seed {humanize.seed} to get this take again)")
    return 0


def summary(score: Score, seconds: float, out: Path | None) -> str:
    minutes, secs = divmod(round(seconds), 60)
    head = f"wrote {out}" if out else "ok"
    lines = [f"{head}: {_plural(score.bars, 'bar')}, {minutes}:{secs:02d}, {_plural(len(score.tracks), 'track')}"]
    width = max(len(t.name) for t in score.tracks)
    for t in score.tracks:
        if t.drums:
            instrument = "drums"
        elif t.program is not None:
            instrument = tables.GM_PROGRAMS[t.program]
        else:
            instrument = "(no program)"
        lines.append(f"  {t.name:<{width}}  ch {t.channel + 1:<2}  {instrument:<22}  {_plural(len(t.notes), 'note')}")
    return "\n".join(lines)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


if __name__ == "__main__":
    sys.exit(main())
