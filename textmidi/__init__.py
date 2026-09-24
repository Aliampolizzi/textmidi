"""textmidi: write music as plain text, get a multi-track MIDI file for a DAW.

    from textmidi import convert
    convert(open("song.txt").read()).save("song.mid")

The score format is documented in MODEL_PROMPT.md.
"""
from __future__ import annotations

import mido

from .model import Issue, Score, ScoreError
from .parser import parse
from .writer import Humanize, build_midi

__all__ = ["Humanize", "Issue", "Score", "ScoreError", "build_midi", "convert", "parse"]


def convert(text: str, *, lenient: bool = False, humanize: Humanize | None = None) -> mido.MidiFile:
    """Parse a score and return a mido.MidiFile ready to .save(). Raises ScoreError."""
    return build_midi(parse(text, lenient=lenient), humanize)
