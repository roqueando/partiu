"""Generate Windows/macOS app icons from the source PNGs using Pillow."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

WIN_SRC = ROOT / "ms-icon-144x144.png"
WIN_OUT = ROOT / "partiu.ico"
WIN_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)]

MAC_SRC = ROOT / "src" / "apple-icon.png"
MAC_OUT = ROOT / "partiu.icns"
MAC_SIZES = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512)]


def make_ico() -> Path:
    Image.open(WIN_SRC).save(WIN_OUT, sizes=WIN_SIZES)
    return WIN_OUT


def make_icns() -> Path:
    Image.open(MAC_SRC).save(MAC_OUT, format="ICNS", sizes=MAC_SIZES)
    return MAC_OUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["ico", "icns", "all"])
    args = parser.parse_args()

    outputs: list[Path] = []
    if args.kind in ("ico", "all"):
        outputs.append(make_ico())
    if args.kind in ("icns", "all"):
        outputs.append(make_icns())

    for path in outputs:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
