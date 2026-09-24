# textmidi

textmidi turns music written as plain text into a multi-track `.mid` file that any DAW can import. It is built so that language models can write the text, since they can't produce binary MIDI themselves.

```
title "Night Drive"
tempo 96
key Am

track Keys  program=electric_piano_1
| [A3 C4 E4 G4]:w | [F3 A3 C4 E4]:w |

track Bass  program=electric_bass_finger
| A1:q. A1:e r A1 C2 E2 | F1:q. F1:e r F1 A1 C2 |
```

## Install

```powershell
git clone https://github.com/Aliampolizzi/textmidi
cd textmidi
py -m pip install -e .[dev]
```

This installs `mido`, plus `pytest` for the tests. On macOS or Linux, use `python3` in place of `py`. After that, `py -m textmidi` works from any folder. A `textmidi` command also works if Python's `Scripts` folder is on your PATH.

## Use

```powershell
py -m textmidi song.txt                      # writes song.mid next to it
py -m textmidi song.txt -o out\take1.mid
py -m textmidi song.txt --humanize           # loosen timing and velocity; prints the seed
py -m textmidi song.txt --humanize --seed 42 # reproduce a take you liked
py -m textmidi song.txt --check              # validate and summarise, write nothing
py -m textmidi song.txt --lenient            # wrong-length bars become warnings
Get-Clipboard | py -m textmidi - -o song.mid # convert straight from the clipboard
```

The input can be a raw score or a whole chat reply. If the file contains Markdown code fences, textmidi uses the ```` ```textmidi ```` block, or else the first fenced block, so you can paste a model's answer as-is.

Errors point at the exact spot:

```
song.txt:14:22: error: track 'Bass': bar 7 has 3.5 beats, but a 4/4 bar has 4
```

Humanize options:
- `--timing-jitter TICKS`: timing spread in ticks, at 480 per beat (default 6)
- `--vel-jitter N`: velocity spread (default 5)

Controllers and pedal events are never jittered. Add `humanize=off` to a `track` line to keep that track exactly on the grid.

## Getting other models to write scores

[MODEL_PROMPT.md](MODEL_PROMPT.md) is the complete spec, written as instructions to a model. It covers:
- the syntax
- the instrument and drum tables
- a checklist of common mistakes
- worked examples

To use it:
1. Paste the whole file into the model's system prompt or first message, followed by your request (for example "a 32-bar lo-fi track in D minor, 80 bpm, keys, bass, drums").
2. Save the reply to a file.
3. Run `py -m textmidi reply.txt`.

If the converter reports an error, paste the error back to the model and ask it to fix that bar.

Every example in MODEL_PROMPT.md is parsed by the test suite, so the spec can't drift from the code.

## In the DAW

- The file is Standard MIDI Type 1:
  - track 0 holds the tempo, time signature and key
  - each `track` becomes a named MIDI track on its own channel
  - drums are on channel 10
- Program changes pick a General MIDI sound. That only matters with a GM synth. With your own instruments or VSTs, just choose the sound on each track.
- **Octave labels differ between DAWs.** textmidi follows the scientific convention, where `C4` is middle C (MIDI note 60). Ableton, Cubase and Logic show that note as C3, and FL Studio shows it as C5. The notes are the same; only the label changes.
- For a quick listen without a DAW, `start song.mid` plays the file through Windows' built-in GS synth.

## Layout

| file | role |
|---|---|
| `textmidi/lexer.py` | code-fence extraction, tokens, `define` patterns, `( … ) xN` repeats |
| `textmidi/parser.py` | tracks, notes, chords, ties, `@` directives and ramps |
| `textmidi/validate.py` | bar-line checks against the time-signature map, track-length warnings |
| `textmidi/writer.py` | MIDI output, event ordering, overlap cleanup, humanize |
| `textmidi/tables.py` | pitches, durations, GM instruments, GM drum map |

Run the tests with `py -m pytest` from this folder.

## License

MIT. See [LICENSE](LICENSE).
