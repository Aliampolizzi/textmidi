"""The spec handed to other models must only show scores that convert cleanly."""
import re
from pathlib import Path

import pytest

from textmidi import convert, parse

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = re.findall(r"```textmidi\n(.*?)```", (ROOT / "MODEL_PROMPT.md").read_text(encoding="utf-8"), re.S)


def test_prompt_has_examples():
    assert len(BLOCKS) >= 8


@pytest.mark.parametrize("block", BLOCKS, ids=[f"block{i}" for i in range(len(BLOCKS))])
def test_prompt_example_converts_without_warnings(block):
    score = parse(block)
    assert score.warnings == []
    convert(block)


def test_demo_converts_without_warnings():
    score = parse((ROOT / "examples" / "demo.txt").read_text(encoding="utf-8"))
    assert score.warnings == []
    assert score.bars == 16
