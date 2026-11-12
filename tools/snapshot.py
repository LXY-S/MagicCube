#!/usr/bin/env python3
"""Render a screenshot of the app offscreen.

Examples:
    .venv/bin/python tools/snapshot.py docs/initial.png --step 0
    .venv/bin/python tools/snapshot.py docs/midway.png --step mid
    .venv/bin/python tools/snapshot.py docs/solved.png --step all
    .venv/bin/python tools/snapshot.py docs/method.png --method cfop --step mid
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rubik.methods import METHODS  # noqa: E402


def _parse_steps(value: str) -> str | int:
    if value in ("mid", "all"):
        return value
    try:
        steps = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an integer, 'mid' or 'all'") from exc
    return max(0, steps)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out",
        nargs="?",
        default="screenshots/app.png",
        help="output PNG path (default: screenshots/app.png)",
    )
    parser.add_argument(
        "--step",
        type=_parse_steps,
        default=None,
        help="advance N plan steps before capturing; also accepts 'mid' or 'all'",
    )
    parser.add_argument("--scramble", default=None, help="use this scramble")
    parser.add_argument(
        "--method",
        default="kociemba",
        choices=[method.id for method in METHODS],
        help="restoration method (default: kociemba)",
    )
    parser.add_argument(
        "--editor",
        action="store_true",
        help="capture the sticker editor dialog instead of the main window",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=830)
    parser.add_argument(
        "--scale", type=int, default=2, help="device pixel ratio (default: 2)"
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=1440,
        help="downscale the capture to this width (0 keeps full size)",
    )
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if args.scale > 1:
        os.environ["QT_SCALE_FACTOR"] = str(args.scale)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    from main import create_app
    from rubik.window import MainWindow

    app = create_app([])
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(args.width, args.height)
    window.show()
    app.processEvents()

    if args.method != window.method_id:
        index = window.method_combo.findData(args.method)
        if index >= 0:
            window.method_combo.setCurrentIndex(index)
            app.processEvents()

    if args.scramble:
        window.load_scramble(args.scramble, animate=False)
        app.processEvents()

    if args.step is not None:
        steps = args.step
        if steps == "mid":
            steps = max(1, len(window.plan) // 2)
        elif steps == "all":
            steps = len(window.plan)
        window.advance_plan_instantly(steps)
        window._cancel_celebration()
        app.processEvents()

    if args.editor:
        from rubik.facelets import cube_to_facelets
        from rubik.sticker_dialog import StickerEditorDialog

        dialog = StickerEditorDialog(
            cube_to_facelets(window.cube),
            window,
            method_id=window.method_id,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        dialog.resize(600, 720)
        dialog.show()
        app.processEvents()
        pixmap = dialog.grab()
        dialog.close()
    else:
        pixmap = window.grab()
    image: QImage = pixmap.toImage()
    if args.max_width and image.width() > args.max_width:
        image = image.scaledToWidth(
            args.max_width, Qt.TransformationMode.SmoothTransformation
        )

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(out), "PNG"):
        print(f"failed to save {out}", file=sys.stderr)
        return 1
    print(f"saved {out} ({image.width()}x{image.height()})")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
