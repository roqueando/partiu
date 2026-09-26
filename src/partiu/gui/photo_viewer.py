"""Full-size photo viewer with a circular 1:1 magnifier lens.

The lens follows the cursor and shows the region under it at 1:1 (one image
pixel per screen pixel), never upscaled.
"""

from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

LENS_SIZE = 160  # lens diameter in screen px (also the source-pixel region size)
MOVE_THRESHOLD = 3  # px of cursor movement before re-rendering the lens


class PhotoViewer(tk.Toplevel):
    """A window showing ``image`` with a magnifier lens that follows the cursor."""

    def __init__(self, parent, image: Image.Image, title: str = "Photo"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)

        self._image = image.convert("RGBA")
        self._photo = None       # ImageTk of the fit-scaled base image
        self._lens_photo = None  # ImageTk of the lens crop
        self._scale = 1.0
        self._offset = (0, 0)    # top-left of the displayed image (canvas coords)
        self._last_pos: tuple[int, int] | None = None

        self.canvas = tk.Canvas(self, background="#222", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        hint = tk.Label(
            self,
            text="Move the mouse over the photo to magnify (1:1)",
            fg="#888",
        )
        hint.pack(fill="x", padx=6, pady=4)

        self.geometry("900x700")
        self.minsize(400, 300)

        self.canvas.bind("<Configure>", lambda _e: self._render_fit())
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)

    # ------------------------------------------------------------------ render

    def _render_fit(self) -> None:
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = self._image.size
        self._scale = min(cw / iw, ch / ih, 1.0)  # never beyond 100%
        disp_w = max(int(iw * self._scale), 1)
        disp_h = max(int(ih * self._scale), 1)
        self._offset = ((cw - disp_w) // 2, (ch - disp_h) // 2)

        disp = (
            self._image.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
            if self._scale < 1.0
            else self._image
        )
        self._photo = ImageTk.PhotoImage(disp)

        self.canvas.delete("all")
        self.canvas.create_image(
            self._offset[0], self._offset[1], anchor="nw", image=self._photo
        )

    def _image_coords(self, cx: float, cy: float) -> tuple[int, int]:
        return (
            int((cx - self._offset[0]) / self._scale),
            int((cy - self._offset[1]) / self._scale),
        )

    # -------------------------------------------------------------------- lens

    def _on_motion(self, event: tk.Event) -> None:
        if self._last_pos is not None:
            if (
                abs(event.x - self._last_pos[0]) < MOVE_THRESHOLD
                and abs(event.y - self._last_pos[1]) < MOVE_THRESHOLD
            ):
                return
        self._last_pos = (event.x, event.y)

        ix, iy = self._image_coords(event.x, event.y)
        iw, ih = self._image.size
        if ix < 0 or iy < 0 or ix >= iw or iy >= ih:
            self._hide_lens()
            return
        self._render_lens(ix, iy, event.x, event.y)

    def _render_lens(self, ix: int, iy: int, cx: int, cy: int) -> None:
        half = LENS_SIZE // 2
        iw, ih = self._image.size
        box = (
            max(ix - half, 0),
            max(iy - half, 0),
            min(ix + half, iw),
            min(iy + half, ih),
        )
        crop = self._image.crop(box)  # 1:1 — no resize

        size = LENS_SIZE
        lens_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        cw, ch = crop.size
        lens_img.paste(crop, ((size - cw) // 2, (size - ch) // 2))
        lens_img.putalpha(mask)

        self._lens_photo = ImageTk.PhotoImage(lens_img)

        self.canvas.delete("lens")
        self.canvas.create_image(cx, cy, image=self._lens_photo, tags="lens")
        self.canvas.create_oval(
            cx - half, cy - half, cx + half, cy + half,
            outline="#fff", width=2, tags="lens",
        )

    def _hide_lens(self) -> None:
        self.canvas.delete("lens")

    def _on_leave(self, _event: tk.Event) -> None:
        self._last_pos = None
        self._hide_lens()
