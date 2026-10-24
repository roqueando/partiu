"""Standalone launcher: open the PIC10/12/16 programmer dialog directly.

Runs the kitsrus K150 programmer tool without the full Partiu app, so it only
needs ``pyserial`` + ``tkinter`` (no PDF/OCR/camera dependencies):

    poetry run python scripts/pic_programmer.py

Or, with the package installed, simply:

    python scripts/pic_programmer.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

# Make the ``partiu`` package importable when running the script directly from
# a source checkout (no install needed).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partiu.gui.tools.pic_programmer import PicProgrammerDialog  # noqa: E402


def main() -> int:
    root = tk.Tk()
    # Hide the root window without unmapping it — a withdrawn root also hides
    # its transient children on macOS, so make it transparent instead.
    root.attributes("-alpha", 0.0)
    dialog = PicProgrammerDialog(root)
    dialog.lift()
    root.wait_window(dialog)  # block until the dialog is closed
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
