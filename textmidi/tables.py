"""Lookup tables and small parsers for pitches, durations, instruments and drums."""
from __future__ import annotations

import difflib
import re
from fractions import Fraction

# --- pitches ---------------------------------------------------------------

_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTALS = {"": 0, "#": 1, "##": 2, "b": -1, "bb": -2}
_PITCH_RE = re.compile(r"([A-G])(##|#|bb|b)?(-1|\d)")
_RAW_PITCH_RE = re.compile(r"n(\d{1,3})")
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def parse_pitch(text: str) -> int | None:
    """MIDI number for 'C4', 'F#3', 'Bb2' or 'n60' (C4 = 60), or None if it isn't a pitch.

    The result may fall outside 0-127; the caller range-checks it.
    """
    m = _RAW_PITCH_RE.fullmatch(text)
    if m:
        return int(m.group(1))
    m = _PITCH_RE.fullmatch(text)
    if not m:
        return None
    letter, accidental, octave = m.groups()
    return 12 * (int(octave) + 1) + _LETTERS[letter] + _ACCIDENTALS[accidental or ""]


def pitch_name(n: int) -> str:
    return f"{_NAMES[n % 12]}{n // 12 - 1}"


# --- durations -------------------------------------------------------------

_BASE_DURATIONS = {
    "w": Fraction(4),
    "h": Fraction(2),
    "q": Fraction(1),
    "e": Fraction(1, 2),
    "s": Fraction(1, 4),
    "t": Fraction(1, 8),
}
_DURATION_RE = re.compile(r"([whqest])(\.{0,2})(3?)")
_NUMBER_RE = re.compile(r"\d+(\.\d+)?|\d+/\d+")


def parse_duration(text: str) -> Fraction | None:
    """Length in quarter-note beats for 'q', 'e.', 'e3', '1.5' or '1/3', or None if invalid."""
    m = _DURATION_RE.fullmatch(text)
    if m:
        base, dots, triplet = m.groups()
        d = _BASE_DURATIONS[base]
        if dots == ".":
            d *= Fraction(3, 2)
        elif dots == "..":
            d *= Fraction(7, 4)
        if triplet:
            d *= Fraction(2, 3)
        return d
    if _NUMBER_RE.fullmatch(text):
        try:
            d = Fraction(text)
        except ZeroDivisionError:
            return None
        return d if d > 0 else None
    return None


def fmt_beats(x: Fraction) -> str:
    """'4', '3.5', '0.25' or '10/3': a decimal when it is exact, else a fraction."""
    if x.denominator == 1:
        return str(x.numerator)
    d = x.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    if d == 1:
        return f"{float(x):g}"
    return f"{x.numerator}/{x.denominator}"


# --- dynamics and controllers ----------------------------------------------

DYNAMICS = {"ppp": 16, "pp": 33, "p": 49, "mp": 64, "mf": 80, "f": 96, "ff": 112, "fff": 127}

CC_ALIASES = {"mod": 1, "breath": 2, "vol": 7, "pan": 10, "expr": 11}

# --- instruments -----------------------------------------------------------

GM_PROGRAMS = [
    # 0 pianos
    "acoustic_grand_piano", "bright_acoustic_piano", "electric_grand_piano", "honky_tonk_piano",
    "electric_piano_1", "electric_piano_2", "harpsichord", "clavinet",
    # 8 chromatic percussion
    "celesta", "glockenspiel", "music_box", "vibraphone",
    "marimba", "xylophone", "tubular_bells", "dulcimer",
    # 16 organs
    "drawbar_organ", "percussive_organ", "rock_organ", "church_organ",
    "reed_organ", "accordion", "harmonica", "tango_accordion",
    # 24 guitars
    "acoustic_guitar_nylon", "acoustic_guitar_steel", "electric_guitar_jazz", "electric_guitar_clean",
    "electric_guitar_muted", "overdriven_guitar", "distortion_guitar", "guitar_harmonics",
    # 32 basses
    "acoustic_bass", "electric_bass_finger", "electric_bass_pick", "fretless_bass",
    "slap_bass_1", "slap_bass_2", "synth_bass_1", "synth_bass_2",
    # 40 strings
    "violin", "viola", "cello", "contrabass",
    "tremolo_strings", "pizzicato_strings", "orchestral_harp", "timpani",
    # 48 ensembles
    "string_ensemble_1", "string_ensemble_2", "synth_strings_1", "synth_strings_2",
    "choir_aahs", "voice_oohs", "synth_voice", "orchestra_hit",
    # 56 brass
    "trumpet", "trombone", "tuba", "muted_trumpet",
    "french_horn", "brass_section", "synth_brass_1", "synth_brass_2",
    # 64 reeds
    "soprano_sax", "alto_sax", "tenor_sax", "baritone_sax",
    "oboe", "english_horn", "bassoon", "clarinet",
    # 72 pipes
    "piccolo", "flute", "recorder", "pan_flute",
    "blown_bottle", "shakuhachi", "whistle", "ocarina",
    # 80 synth leads
    "lead_1_square", "lead_2_sawtooth", "lead_3_calliope", "lead_4_chiff",
    "lead_5_charang", "lead_6_voice", "lead_7_fifths", "lead_8_bass_lead",
    # 88 synth pads
    "pad_1_new_age", "pad_2_warm", "pad_3_polysynth", "pad_4_choir",
    "pad_5_bowed", "pad_6_metallic", "pad_7_halo", "pad_8_sweep",
    # 96 synth effects
    "fx_1_rain", "fx_2_soundtrack", "fx_3_crystal", "fx_4_atmosphere",
    "fx_5_brightness", "fx_6_goblins", "fx_7_echoes", "fx_8_sci_fi",
    # 104 ethnic
    "sitar", "banjo", "shamisen", "koto",
    "kalimba", "bagpipe", "fiddle", "shanai",
    # 112 percussive
    "tinkle_bell", "agogo", "steel_drums", "woodblock",
    "taiko_drum", "melodic_tom", "synth_drum", "reverse_cymbal",
    # 120 sound effects
    "guitar_fret_noise", "breath_noise", "seashore", "bird_tweet",
    "telephone_ring", "helicopter", "applause", "gunshot",
]
assert len(GM_PROGRAMS) == 128

PROGRAM_ALIASES = {
    "piano": 0, "grand_piano": 0, "bright_piano": 1,
    "epiano": 4, "electric_piano": 4, "rhodes": 4,
    "organ": 16, "rock_organ": 18,
    "guitar": 25, "acoustic_guitar": 25, "nylon_guitar": 24, "steel_guitar": 25,
    "jazz_guitar": 26, "electric_guitar": 27, "clean_guitar": 27, "muted_guitar": 28,
    "overdrive_guitar": 29, "distortion": 30,
    "bass": 33, "electric_bass": 33, "finger_bass": 33, "pick_bass": 34,
    "upright_bass": 32, "slap_bass": 36, "synth_bass": 38,
    "strings": 48, "string_ensemble": 48, "synth_strings": 50, "harp": 46, "pizzicato": 45,
    "choir": 52, "voice": 53,
    "horn": 60, "brass": 61, "synth_brass": 62,
    "sax": 65, "saxophone": 65,
    "square": 80, "square_lead": 80, "saw": 81, "sawtooth": 81, "saw_lead": 81,
    "pad": 89, "warm_pad": 89,
}

_PROGRAM_INDEX = {name: i for i, name in enumerate(GM_PROGRAMS)}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def resolve_program(text: str) -> int:
    """Program number (0-127) for a GM name, an alias or a number. Raises ValueError."""
    if text.isdigit():
        n = int(text)
        if n > 127:
            raise ValueError(f"program {n} is out of range (0-127)")
        return n
    slug = _slug(text)
    if slug in _PROGRAM_INDEX:
        return _PROGRAM_INDEX[slug]
    if slug in PROGRAM_ALIASES:
        return PROGRAM_ALIASES[slug]
    raise ValueError(f"unknown instrument '{text}'" + suggest(slug, [*GM_PROGRAMS, *PROGRAM_ALIASES]))


# --- drums (GM percussion map, channel 10) ----------------------------------

DRUMS = {
    "kick2": 35, "kick": 36, "rim": 37, "snare": 38, "clap": 39, "snare2": 40,
    "tom_floor_low": 41, "hat": 42, "tom_floor": 43, "hat_pedal": 44, "tom_low": 45,
    "hat_open": 46, "tom_mid": 47, "tom_high_mid": 48, "crash": 49, "tom_high": 50,
    "ride": 51, "china": 52, "ride_bell": 53, "tambourine": 54, "splash": 55,
    "cowbell": 56, "crash2": 57, "vibraslap": 58, "ride2": 59,
    "bongo_high": 60, "bongo_low": 61, "conga_mute": 62, "conga_high": 63, "conga_low": 64,
    "timbale_high": 65, "timbale_low": 66, "agogo_high": 67, "agogo_low": 68,
    "cabasa": 69, "maracas": 70, "whistle_short": 71, "whistle_long": 72,
    "guiro_short": 73, "guiro_long": 74, "claves": 75, "woodblock_high": 76,
    "woodblock_low": 77, "cuica_mute": 78, "cuica_open": 79,
    "triangle_mute": 80, "triangle_open": 81,
}

DRUM_ALIASES = {
    "bd": "kick", "sd": "snare", "hh": "hat", "oh": "hat_open", "cr": "crash", "rd": "ride",
    "tom_low_mid": "tom_mid", "tamb": "tambourine", "shaker": "maracas", "sidestick": "rim",
}


def drum_note(text: str) -> int | None:
    return DRUMS.get(DRUM_ALIASES.get(text, text))


# --- key signatures --------------------------------------------------------

_KEYS = {
    "Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#",
    "Abm", "Ebm", "Bbm", "Fm", "Cm", "Gm", "Dm", "Am", "Em", "Bm", "F#m", "C#m", "G#m", "D#m", "A#m",
}
_KEY_RE = re.compile(r"([A-Ga-g])([#b]?)\s*(m|min|minor|maj|major)?")


def parse_key(text: str) -> str | None:
    """Normalise 'Am', 'A minor', 'Bb', 'F# major' to a MIDI key name, or None."""
    m = _KEY_RE.fullmatch(text.strip())
    if not m:
        return None
    letter, accidental, mode = m.groups()
    name = letter.upper() + accidental + ("m" if mode in ("m", "min", "minor") else "")
    return name if name in _KEYS else None


# --- misc ------------------------------------------------------------------


def suggest(word: str, choices) -> str:
    close = difflib.get_close_matches(word, list(choices), n=3, cutoff=0.6)
    if not close:
        return ""
    return " (did you mean " + " or ".join(f"'{c}'" for c in close) + "?)"
