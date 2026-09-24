# textmidi: writing music the converter can read

You are writing music in **textmidi**, a plain-text score format. A converter turns your score into a standard multi-track MIDI file, which the user opens in a DAW. The converter is strict. If one bar doesn't add up, or one name is misspelled, it rejects the whole score. Follow this spec exactly and don't invent syntax.

## How to answer

1. Put the whole score in **one** fenced code block tagged `textmidi`. You may add a sentence or two outside the block. Inside the block, write only textmidi; use `#` comments for any notes to the reader.
2. Write bar lines `|` around every bar, and make every bar add up exactly (see [Bar lines](#bar-lines)).
3. End every track at the same point. Pad with rests.
4. Use only the names listed here for instruments, drums, options and directives.

## A minimal score

```textmidi
title "Minimal"
tempo 100
time 4/4

track Melody  program=flute
| C5:q D5 E5 G5 | A5:h G5:h |

track Chords  program=acoustic_grand_piano  vel=64
| [C4 E4 G4]:w | [F3 A3 C4]:h [G3 B3 D4]:h |
```

A score is an optional **header** followed by one or more **tracks**. A `#` at the start of a word begins a comment that runs to the end of the line. Inside a track, spacing and line breaks don't matter.

## Header

These lines go before the first track. All of them are optional.

| line | meaning | default |
|---|---|---|
| `title "Name"` | song name | none |
| `tempo 96` | quarter-note beats per minute | 120 |
| `time 3/4` | time signature | 4/4 |
| `key Am` | key signature, for display only: `C`, `F#`, `Bb`, `Am`, `C#m` … (it does not transpose) | none |

## Tracks

`track NAME option=value …` starts a track. Its music goes on the following lines, up to the next `track`. If the name has spaces, quote it: `track "Piano RH"`.

| option | meaning | default |
|---|---|---|
| `program=` | instrument: a GM name from [Instruments](#instruments), such as `electric_piano_1`, an alias such as `strings`, or a number 0–127 | none; the DAW decides |
| `drums` | drum track: channel 10, notes are [drum names](#drums) | off |
| `channel=` | MIDI channel 1–16 | assigned automatically, skipping 10 |
| `vel=` | starting velocity 1–127, or a dynamic such as `mf` | 80 |
| `gate=` | fraction of each written length that actually sounds; `0.5` is staccato | 1.0 |
| `bendrange=` | pitch-bend range in semitones | 2 |
| `humanize=off` | leave this track out when the user converts with `--humanize` | on |

A track plays one rhythm at a time: single notes or chords. When an instrument needs two independent rhythms, such as a pianist's two hands, write two tracks with the same `channel=` and `program=`:

```textmidi
track "Piano RH"  program=piano  channel=1
| E5:q D5 C5 D5 | E5:h E5:h |

track "Piano LH"  program=piano  channel=1
| [C3 G3]:w | [C3 G3]:w |
```

## Notes

A note is `PITCH:DURATION`, for example `C4:q`, `F#3:e.` or `Bb5:h`.

### Pitch

- A letter `A`–`G` (uppercase), then an optional accidental (`#`, `##`, `b`, `bb`), then an octave from `-1` to `9`.
- `C4` is middle C (MIDI 60), and `A4` is 440 Hz. The octave number goes up at C, so `B3` sits just below `C4`.
- `n60` gives a raw MIDI note number.
- Typical ranges:
  - bass guitar `E1`–`G3`
  - cello `C2`–`A4`
  - guitar `E2`–`E5`
  - piano chords `C3`–`C5`
  - vocal-range melodies `C4`–`C6`
  - flute `C4`–`C7`

### Duration

Durations are counted in **quarter-note beats**, whatever the time signature.

| token | name | beats |
|---|---|---|
| `w` | whole | 4 |
| `h` | half | 2 |
| `q` | quarter | 1 |
| `e` | eighth | 1/2 |
| `s` | sixteenth | 1/4 |
| `t` | thirty-second | 1/8 |

- **Dots:** `q.` = 1.5, `h.` = 3, `e.` = 0.75. A double dot: `q..` = 1.75.
- **Triplets:** add `3`. `e3` = 1/3 beat (three per beat), `q3` = 2/3 beat (three per half note), `s3` = 1/6 beat.
- **Numbers:** `:1.5`, `:3` and `:1/3` are lengths in beats.
- **Sticky duration:** a note, rest or chord written without `:DURATION` reuses the previous duration in the same track. Before the first duration in a track, the default is `q`. So `C4:e D4 E4 F4` is four eighth notes. This carries across bar lines and into and out of patterns. When in doubt, write the duration.

```textmidi
track Lead  program=flute
| C5:e3 D5 E5 F5:q G5:h | A5:q. G5:e F5:s E5 D5 C5 B4:q | C5:w |
```

### Rests, chords, ties

- **Rest:** `r` or `r:h`.
- **Chord:** `[C4 E4 G4]:h`. The pitches go inside the brackets and the duration goes after the closing bracket.
- **Tie:** `~` after a note joins it to the next note of the same pitch, including across a bar line. `| C4:w~ | C4:h r:h |` sounds as one six-beat C. On a chord, `]~` ties every pitch; `[C4~ E4 G4]` ties only the C.

```textmidi
track Strings  program=strings
| [A3 C4 E4]:w~ | [A3 C4 E4]:h [A3 D4 F4]:h |
| [G3~ B3 D4]:h [G3 C4 E4]:h | r:w |
```

### Velocity and accents

- A track starts at its `vel=`, which defaults to 80.
- Dynamics change the velocity of every note that follows:

  | dynamic | `@ppp` | `@pp` | `@p` | `@mp` | `@mf` | `@f` | `@ff` | `@fff` |
  |---|---|---|---|---|---|---|---|---|
  | velocity | 16 | 33 | 49 | 64 | 80 | 96 | 112 | 127 |

  `@vel=90` sets an exact velocity.
- On a single note, `>` is an accent that adds 20 (`snare:q>`), and `!NN` sets that note's velocity exactly (`snare:s!35` is a ghost note).
- Suffix order: pitch, then `:duration`, then any of `~` `>` `!NN`, for example `C4:q.~>`.

## Bar lines

`|` is a bar line. **Every `|` must land exactly on a bar boundary.** The converter checks this and rejects the score otherwise, with an error like `bar 7 has 3.5 beats, but a 4/4 bar has 4`. Start and end each bar with `|`. Two in a row (`| |`) are harmless.

Bar length in beats = numerator × 4 ÷ denominator:

| time | 4/4 | 3/4 | 2/4 | 2/2 | 6/8 | 9/8 | 12/8 | 5/4 | 7/8 |
|---|---|---|---|---|---|---|---|---|---|
| beats per bar | 4 | 3 | 2 | 4 | 3 | 4.5 | 6 | 5 | 3.5 |

```textmidi
time 6/8
track Guitar  program=acoustic_guitar_nylon
| A3:e C4 E4 A4 E4 C4 | G3:q. B3:q. |
```

## Repeats and patterns

- **Repeat:** `( … ) x4` plays the contents four times. Repeats can nest.
- **Pattern:** `define NAME { … }` goes outside any track, usually right after the header. Inside a track, `$NAME` plays it once and `$NAME x8` plays it eight times. A pattern is pasted in as text, so it can contain bar lines, directives, repeats and other patterns.
- Start every pattern with an explicit duration, so a sticky duration from before it can't leak in.
- Use patterns for grooves, riffs and repeated sections. They keep long songs short.

```textmidi
define riff { | A2:e A2 C3 A2 D3 A2 C3 B2 | }

track Bass  program=synth_bass
$riff x3 | ( F2:e F2 A2 F2 ) x2 |
```

## Directives

A directive starts with `@`. It acts at its position in the track and takes no time.

| directive | effect |
|---|---|
| `@mf`, `@vel=90` | velocity of the notes that follow |
| `@gate=0.5` | gate of the notes that follow |
| `@program=strings` | switch instrument |
| `@tempo=80` | tempo change for the whole song; put these in the first track |
| `@time=3/4` | time-signature change for the whole song; must sit on a bar line; first track |
| `@sustain=on`, `@sustain=off` | sustain pedal (CC64) |
| `@mod=V` | mod wheel (CC1), 0–127 |
| `@expr=V` | expression (CC11), 0–127 |
| `@vol=V` | channel volume (CC7), 0–127 |
| `@pan=V` | pan (CC10): 0 left, 64 center, 127 right |
| `@breath=V` | breath (CC2), 0–127 |
| `@ccN=V` | any controller, e.g. `@cc74=100` |
| `@bend=S` | pitch bend in semitones, within ±bendrange; `@bend=0` resets |

### Ramps

`@expr=40..110:w` moves from 40 to 110 over a whole note. A ramp starts at its position and runs underneath the notes that follow. It takes no time itself. Ramps work with `@mod`, `@expr`, `@vol`, `@pan`, `@breath`, `@ccN` and `@bend`.

```textmidi
track Lead  program=violin
| @expr=40..120:w C5:w | A4:h. @bend=0..2:q A4:q |
| @bend=0 B4:w |
```

- **Sustain pedal:** press the pedal with a chord. At each chord change, lift it and press it again (`@sustain=off @sustain=on [F3 A3 C4]:w`). Lift it at the end.
- **Bends:** after a bend, return it to 0 (`@bend=0`) before any note that shouldn't be bent.
- **Vibrato:** use `@mod`, for example `@mod=0..90:w` to fade vibrato in and `@mod=0` to turn it off.

## Drums

Mark a drum track with `drums`. Its notes are drum names, or numbers written like `n36`. Durations work as usual and set the spacing between hits. Write simultaneous hits as chords.

```textmidi
define beat {
  | [kick hat]:e hat [snare hat] hat [kick hat] [kick hat] [snare hat] hat |
}

track Drums  drums
$beat x3
| [kick hat]:e hat [snare hat] hat snare:s!50 snare!65 snare!80 snare!95 tom_high:s tom_mid tom_low tom_floor |
| [kick crash]:w |
```

| name | note | name | note | name | note |
|---|---|---|---|---|---|
| `kick` | 36 | `hat` | 42 | `tom_floor_low` | 41 |
| `kick2` | 35 | `hat_pedal` | 44 | `tom_floor` | 43 |
| `snare` | 38 | `hat_open` | 46 | `tom_low` | 45 |
| `snare2` | 40 | `crash` | 49 | `tom_mid` | 47 |
| `rim` | 37 | `crash2` | 57 | `tom_high_mid` | 48 |
| `clap` | 39 | `ride` | 51 | `tom_high` | 50 |
| `tambourine` | 54 | `ride2` | 59 | `cowbell` | 56 |
| `maracas` | 70 | `ride_bell` | 53 | `claves` | 75 |
| `cabasa` | 69 | `china` | 52 | `vibraslap` | 58 |
| `triangle_mute` | 80 | `splash` | 55 | `woodblock_high` | 76 |
| `triangle_open` | 81 | `bongo_high` | 60 | `woodblock_low` | 77 |
| `conga_mute` | 62 | `bongo_low` | 61 | `agogo_high` | 67 |
| `conga_high` | 63 | `timbale_high` | 65 | `agogo_low` | 68 |
| `conga_low` | 64 | `timbale_low` | 66 | `guiro_short` | 73 |
| `cuica_mute` | 78 | `whistle_short` | 71 | `guiro_long` | 74 |
| `cuica_open` | 79 | `whistle_long` | 72 | | |

Aliases:

| alias | means |
|---|---|
| `bd` | `kick` |
| `sd` | `snare` |
| `hh` | `hat` |
| `oh` | `hat_open` |
| `cr` | `crash` |
| `rd` | `ride` |
| `sidestick` | `rim` |
| `tamb` | `tambourine` |
| `shaker` | `maracas` |
| `tom_low_mid` | `tom_mid` |

## Instruments

These are the General MIDI programs, numbered from 0. Use the name, or the number.

- **0–7 piano:** `acoustic_grand_piano` `bright_acoustic_piano` `electric_grand_piano` `honky_tonk_piano` `electric_piano_1` `electric_piano_2` `harpsichord` `clavinet`
- **8–15 chromatic percussion:** `celesta` `glockenspiel` `music_box` `vibraphone` `marimba` `xylophone` `tubular_bells` `dulcimer`
- **16–23 organ:** `drawbar_organ` `percussive_organ` `rock_organ` `church_organ` `reed_organ` `accordion` `harmonica` `tango_accordion`
- **24–31 guitar:** `acoustic_guitar_nylon` `acoustic_guitar_steel` `electric_guitar_jazz` `electric_guitar_clean` `electric_guitar_muted` `overdriven_guitar` `distortion_guitar` `guitar_harmonics`
- **32–39 bass:** `acoustic_bass` `electric_bass_finger` `electric_bass_pick` `fretless_bass` `slap_bass_1` `slap_bass_2` `synth_bass_1` `synth_bass_2`
- **40–47 strings:** `violin` `viola` `cello` `contrabass` `tremolo_strings` `pizzicato_strings` `orchestral_harp` `timpani`
- **48–55 ensemble:** `string_ensemble_1` `string_ensemble_2` `synth_strings_1` `synth_strings_2` `choir_aahs` `voice_oohs` `synth_voice` `orchestra_hit`
- **56–63 brass:** `trumpet` `trombone` `tuba` `muted_trumpet` `french_horn` `brass_section` `synth_brass_1` `synth_brass_2`
- **64–71 reed:** `soprano_sax` `alto_sax` `tenor_sax` `baritone_sax` `oboe` `english_horn` `bassoon` `clarinet`
- **72–79 pipe:** `piccolo` `flute` `recorder` `pan_flute` `blown_bottle` `shakuhachi` `whistle` `ocarina`
- **80–87 synth lead:** `lead_1_square` `lead_2_sawtooth` `lead_3_calliope` `lead_4_chiff` `lead_5_charang` `lead_6_voice` `lead_7_fifths` `lead_8_bass_lead`
- **88–95 synth pad:** `pad_1_new_age` `pad_2_warm` `pad_3_polysynth` `pad_4_choir` `pad_5_bowed` `pad_6_metallic` `pad_7_halo` `pad_8_sweep`
- **96–103 synth effects:** `fx_1_rain` `fx_2_soundtrack` `fx_3_crystal` `fx_4_atmosphere` `fx_5_brightness` `fx_6_goblins` `fx_7_echoes` `fx_8_sci_fi`
- **104–111 ethnic:** `sitar` `banjo` `shamisen` `koto` `kalimba` `bagpipe` `fiddle` `shanai`
- **112–119 percussive:** `tinkle_bell` `agogo` `steel_drums` `woodblock` `taiko_drum` `melodic_tom` `synth_drum` `reverse_cymbal`
- **120–127 sound effects:** `guitar_fret_noise` `breath_noise` `seashore` `bird_tweet` `telephone_ring` `helicopter` `applause` `gunshot`

Aliases:

| alias | program |
|---|---|
| `piano` | acoustic_grand_piano |
| `epiano`, `rhodes` | electric_piano_1 |
| `organ` | drawbar_organ |
| `guitar` | acoustic_guitar_steel |
| `nylon_guitar` | acoustic_guitar_nylon |
| `clean_guitar`, `electric_guitar` | electric_guitar_clean |
| `distortion` | distortion_guitar |
| `bass` | electric_bass_finger |
| `upright_bass` | acoustic_bass |
| `synth_bass` | synth_bass_1 |
| `strings` | string_ensemble_1 |
| `harp` | orchestral_harp |
| `choir` | choir_aahs |
| `brass` | brass_section |
| `horn` | french_horn |
| `sax` | alto_sax |
| `square` | lead_1_square |
| `saw` | lead_2_sawtooth |
| `pad` | pad_2_warm |

## Checklist: go through it before answering

- [ ] **Count every bar.** Add up the durations between each pair of `|` (q = 1, e = 0.5, s = 0.25, q. = 1.5, h. = 3, e3 = 1/3) and compare with the bar length.
- [ ] **Watch sticky durations.** After `C4:h`, a bare `D4` is also a half note, and a bare `r` is a half rest.
- [ ] **Keep tracks the same length.** Every track ends at the same bar. Pad with `r:w`.
- [ ] **Put `@tempo` and `@time` changes in the first track.** A `@time` change goes right after a bar line.
- [ ] **Write pitches correctly.** Pitches are uppercase with an octave (`C#4`, `Bb3`). Use `#` and `b`, never ♯ or ♭. `C4` is middle C, and bass lines sit in octaves 1–2.
- [ ] **Keep drum names in `drums` tracks.** Drum names are lowercase and only work there.
- [ ] **Put chord durations after the bracket:** `[C4 E4 G4]:h`, not `[C4:h E4 G4]`.
- [ ] **Clean up automation.** Reset bends with `@bend=0` and lift the pedal with `@sustain=off` at the end.
- [ ] **Don't invent syntax.** Directives, options, instruments and drums not listed here are errors.

## Full example

```textmidi
title "Example Song"
tempo 110
time 4/4
key C

define beat {
  | [kick hat]:e hat [snare hat] hat [kick hat] [kick hat] [snare hat] hat |
}
define beat_crash {
  | [kick crash]:e hat [snare hat] hat [kick hat] [kick hat] [snare hat] hat |
}

# C  G  Am  F  |  C  G  Am F  C
track Piano  program=acoustic_grand_piano  vel=70
@sustain=on
| [E3 G3 C4]:h [E3 G3 C4]:h | @sustain=off @sustain=on [D3 G3 B3]:h [D3 G3 B3]:h |
| @sustain=off @sustain=on [E3 A3 C4]:h [E3 A3 C4]:h | @sustain=off @sustain=on [F3 A3 C4]:h [F3 A3 C4]:h |
| @sustain=off @sustain=on [E3 G3 C4]:h [E3 G3 C4]:h | @sustain=off @sustain=on [D3 G3 B3]:h [D3 G3 B3]:h |
| @sustain=off @sustain=on [E3 A3 C4]:h @sustain=off @sustain=on [F3 A3 C4]:h |
| @sustain=off @sustain=on [E3 G3 C4]:w | @sustain=off

track Bass  program=electric_bass_finger  vel=92
| C2:q. C2:e r C2 G1:q | G1:q. G1:e r G1 D2:q | A1:q. A1:e r A1 E2:q | F1:q. F1:e r F1 C2:q |
| C2:q. C2:e r C2 G1:q | G1:q. G1:e r G1 D2:q | A1:h F1:h | C2:w |

track Sax  program=alto_sax  vel=90
| r:q E5:e D5 C5:q D5 | D5:q. B4:e G4:h | C5:q. B4:e A4:q E5 | @expr=70..110:w C5:w |
| @expr=100 r:q E5:e D5 C5:q G5 | G5:q. F5:e D5:h | E5:q. D5:e C5:q A4 | @bend=-1..0:e C5:w |

track Drums  drums  vel=96
$beat_crash $beat x3 $beat_crash $beat x2 | [kick crash]:w |
```
