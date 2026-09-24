# Double-click to open the textmidi window. .pyw runs without a console, so
# a missing package is reported in a message box instead of vanishing.
try:
    from textmidi.gui import main
except ImportError as e:
    from tkinter import messagebox
    messagebox.showerror("textmidi", f"{e}\n\nRun setup.bat first, then try again.")
    raise SystemExit(1)

main()
