"""Record the desktop demo as an animated GIF (docs/demo.gif).

    pip install Pillow
    python demo/make_gif.py

Drives the real window through every scenario (switching pages, selecting rows, opening the
export dialog) and grabs frames. Needs a display (it opens the window briefly).
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402
from PyQt6.QtCore import QBuffer, QIODevice  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import app_qt  # noqa: E402
import ui_theme as theme  # noqa: E402

OUT = os.path.join(HERE, "..", "docs", "demo.gif")
WIDTH = 1000          # output width in px (keeps the file small)


def grab(widget):
    ba = QBuffer(); ba.open(QIODevice.OpenModeFlag.WriteOnly)
    widget.grab().save(ba, "PNG")
    return Image.open(io.BytesIO(bytes(ba.data()))).convert("RGB")


def snap(widget, modal=None):
    """Window frame; a dialog is composited centred over a dimmed window, like a real modal."""
    img = grab(widget)
    if modal is not None:
        img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.35)
        d = grab(modal)
        d = d.crop((0, 0, min(d.width, img.width - 80), min(d.height, img.height - 60)))
        img.paste(d, ((img.width - d.width) // 2, (img.height - d.height) // 2))
    return img.resize((WIDTH, int(img.height * WIDTH / img.width)), Image.LANCZOS)


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    win = app_qt.DemoWindow(); win.show(); app.processEvents()
    frames, delays = [], []

    def hold(ms, modal=None):
        app.processEvents()
        frames.append(snap(win, modal)); delays.append(ms)

    # (page, rows to step through, hold per row in ms)
    for page, hold_ms in [(0, 1100), (1, 1700), (2, 1900), (3, 1900), (4, 1700)]:
        win.load(page); app.processEvents()
        n = len(win.results[page]["rows"])
        for r in range(n):
            win.table.selectRow(r)
            hold(hold_ms if r == 0 or page == 0 else 700)

    dlg = app_qt.ExportDialog([("PO260123", 4), ("PO260124", 2), ("PO260125", 3)], win)
    dlg.show(); app.processEvents(); hold(2400, dlg)
    dlg.close()
    win.load(0); win.table.selectRow(0); hold(1200)

    # one shared palette keeps colours stable between frames
    pal = frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    q[0].save(OUT, save_all=True, append_images=q[1:], duration=delays, loop=0, optimize=True, disposal=1)
    print(f"{len(frames)} frames -> {os.path.normpath(OUT)} ({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
