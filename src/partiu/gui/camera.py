"""Camera capture dialog for taking a component photo on the spot."""

from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import cv2
from PIL import Image, ImageTk

#: Highest camera index probed when listing devices.
_MAX_CAMERAS = 5

#: Preview refresh interval, in milliseconds.
_POLL_MS = 30

#: Fixed live-preview size (pixels).
_PREVIEW_WIDTH = 300
_PREVIEW_HEIGHT = 200


def list_cameras(max_index: int = _MAX_CAMERAS) -> list[tuple[int, str]]:
    """Return ``[(index, label), ...]`` for every camera that opens."""
    cameras: list[tuple[int, str]] = []
    for index in range(max_index + 1):
        cap = cv2.VideoCapture(index)
        try:
            if cap.isOpened():
                cameras.append((index, f"Camera {index}"))
        finally:
            cap.release()
    return cameras


class CameraCaptureDialog(tk.Toplevel):
    """Modal dialog with a live preview and a Capture button.

    After the dialog closes, read :attr:`captured_path`; it is ``None`` when the
    user cancelled or no frame could be captured.
    """

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title("Take photo")
        self.resizable(False, False)
        self.transient(master)

        self.captured_path: Path | None = None
        self._cameras: list[tuple[int, str]] = []
        self._cap: cv2.VideoCapture | None = None
        self._photo_ref: ImageTk.PhotoImage | None = None
        self._after_id: str | None = None

        self._build_ui()
        self._refresh_cameras()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()

    # ------------------------------------------------------------ UI building

    def _build_ui(self) -> None:
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)

        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Camera").pack(side="left")

        self.camera_var = tk.StringVar()
        self.camera_box = ttk.Combobox(
            controls, textvariable=self.camera_var, state="readonly", width=16
        )
        self.camera_box.pack(side="left", padx=(6, 0))
        self.camera_box.bind("<<ComboboxSelected>>", self._on_camera_selected)

        ttk.Button(controls, text="Refresh", command=self._refresh_cameras).pack(
            side="left", padx=(6, 0)
        )

        self.preview = tk.Canvas(
            body,
            width=_PREVIEW_WIDTH,
            height=_PREVIEW_HEIGHT,
            highlightthickness=1,
            relief="solid",
            background="#000",
        )
        self.preview.pack()

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right")
        self.capture_button = ttk.Button(
            buttons, text="Capture", command=self._capture
        )
        self.capture_button.pack(side="right", padx=(0, 6))

    # -------------------------------------------------------------- cameras

    def _refresh_cameras(self) -> None:
        self._stop_capture()
        self._cameras = list_cameras()
        self.camera_box["values"] = [label for _index, label in self._cameras]
        if not self._cameras:
            self.camera_var.set("")
            self._show_unavailable()
            return
        self.camera_box.current(0)
        self.camera_var.set(self._cameras[0][1])
        self._start_capture(self._cameras[0][0])

    def _on_camera_selected(self, _event=None) -> None:
        label = self.camera_var.get()
        for index, camera_label in self._cameras:
            if camera_label == label:
                self._start_capture(index)
                return

    def _start_capture(self, index: int) -> None:
        self._stop_capture()
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            cap.release()
            self._show_unavailable()
            return
        self._cap = cap
        self.preview.delete("all")
        self.capture_button.configure(state="normal")
        self._after_id = self.after(_POLL_MS, self._poll)

    def _stop_capture(self) -> None:
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _poll(self) -> None:
        cap = self._cap
        if cap is None or not cap.isOpened():
            self._show_unavailable()
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            self._after_id = self.after(_POLL_MS, self._poll)
            return
        # BGR -> RGB, then mirror for a natural self-view in the preview.
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.flip(frame, 1)
        image = Image.fromarray(frame)
        image.thumbnail((_PREVIEW_WIDTH, _PREVIEW_HEIGHT), Image.Resampling.LANCZOS)
        self._photo_ref = ImageTk.PhotoImage(image)
        self.preview.delete("all")
        self.preview.create_image(
            _PREVIEW_WIDTH // 2,
            _PREVIEW_HEIGHT // 2,
            image=self._photo_ref,
            anchor="center",
        )
        self._after_id = self.after(_POLL_MS, self._poll)

    def _capture(self) -> None:
        cap = self._cap
        if cap is None or not cap.isOpened():
            self._show_unavailable()
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            messagebox.showerror(
                "Capture", "Could not capture a frame.", parent=self
            )
            return
        # Save unflipped — mirroring only affects the live preview.
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                path = Path(tmp.name)
            image.save(path, "JPEG")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Capture", f"Could not save photo:\n{exc}", parent=self
            )
            return
        self.captured_path = path
        self._close()

    def _show_unavailable(self) -> None:
        self._stop_capture()
        self.preview.delete("all")
        self.preview.create_text(
            _PREVIEW_WIDTH // 2,
            _PREVIEW_HEIGHT // 2,
            text="No camera available",
            fill="#fff",
        )
        self.capture_button.configure(state="disabled")

    def _cancel(self) -> None:
        self._close()

    def _close(self) -> None:
        self._stop_capture()
        self.destroy()
