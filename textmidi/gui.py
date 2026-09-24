"""A small window for converting a score: py -m textmidi.gui"""
from __future__ import annotations

import contextlib
import io
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .__main__ import main as cli_main


def convert(path: str) -> tuple[bool, str]:
    """Convert one score next to itself, as the command line does; return (ok, what it printed)."""
    score = Path(path).resolve()
    if not score.is_file():
        return False, f"Can't find {score}"
    out = io.StringIO()
    cwd = os.getcwd()
    os.chdir(score.parent)  # so messages name the file rather than its whole path
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli_main(["--", score.name])  # "--": a name like "-x.txt" isn't an option
    finally:
        os.chdir(cwd)
    return code == 0, out.getvalue()


def main() -> None:
    root = tk.Tk()
    root.title("textmidi")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(2, weight=1)

    path = tk.StringVar()
    output = tk.Text(root, width=80, height=12, font="TkFixedFont", wrap="word", state="disabled")
    output.tag_configure("error", foreground="#b00020")

    def show(text: str, ok: bool = True) -> None:
        output.configure(state="normal")
        output.delete("1.0", "end")
        output.insert("1.0", text, () if ok else "error")
        output.configure(state="disabled")

    def browse() -> None:
        chosen = filedialog.askopenfilename(
            title="Choose a score",
            filetypes=[("Text scores", "*.txt *.md"), ("All files", "*.*")],
        )
        if chosen:
            path.set(chosen)

    def run() -> None:
        if not path.get().strip():
            show("Choose a score first.", ok=False)
            return
        ok, text = convert(path.get().strip())
        show(text, ok)

    ttk.Entry(root, textvariable=path).grid(row=0, column=0, sticky="ew", padx=(10, 5), pady=10)
    ttk.Button(root, text="Browse...", command=browse).grid(row=0, column=1, padx=(0, 10))
    ttk.Button(root, text="Convert to MIDI", command=run).grid(row=1, column=0, columnspan=2)
    output.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
    root.mainloop()


if __name__ == "__main__":
    main()
