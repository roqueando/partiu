"""Camera driver adapter (cv2), independent of any GUI toolkit."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import cv2
from PIL import Image

from .persistence import UserSettings

#: Highest camera index probed when detecting devices.
_MAX_CAMERAS = 8

#: In-memory cache of detected cameras so reopening is instant.
_camera_cache: list[tuple[int, str]] | None = None

_settings: UserSettings | None = None


def _prefs() -> UserSettings:
    global _settings
    if _settings is None:
        _settings = UserSettings()
    return _settings


def _camera_label(index: int) -> str:
    return f"Camera {index}"


def _open_capture(index: int) -> cv2.VideoCapture | None:
    """Open ``index``, trying the native backend first (AVFoundation on macOS).

    Returns ``None`` when the index cannot be opened by any backend.
    """
    backends: list[int] = []
    if sys.platform == "darwin":
        backends.append(getattr(cv2, "CAP_AVFOUNDATION", cv2.CAP_ANY))
    backends.append(cv2.CAP_ANY)

    seen: set[int] = set()
    for backend in backends:
        if backend in seen:
            continue
        seen.add(backend)
        cap = cv2.VideoCapture(index, backend)
        if cap.isOpened():
            return cap
        cap.release()
    return None


def list_cameras(max_index: int = _MAX_CAMERAS) -> list[tuple[int, str]]:
    """Detect cameras and update the cache.

    Every index is probed: camera indices are not guaranteed to be contiguous
    (e.g. a built-in camera plus a USB microscope on macOS).
    """
    global _camera_cache
    cameras: list[tuple[int, str]] = []
    for index in range(max_index + 1):
        cap = _open_capture(index)
        if cap is None:
            continue
        cap.release()
        cameras.append((index, _camera_label(index)))
    _camera_cache = cameras
    _prefs().set("camera_indices", [index for index, _label in cameras])
    return cameras


def cached_cameras() -> list[tuple[int, str]] | None:
    """Return a cached camera list, or ``None`` if nothing is known yet."""
    if _camera_cache is not None:
        return list(_camera_cache)
    indices = _prefs().get("camera_indices")
    # An empty persisted list is not trusted: re-detect so a camera plugged in
    # since the last (possibly failed) probe is still found.
    if isinstance(indices, list) and indices:
        return [(int(index), _camera_label(int(index))) for index in indices]
    return None


def get_preferred_camera() -> int | None:
    """Return the last-selected camera index, or ``None``."""
    index = _prefs().get("camera_index")
    return int(index) if index is not None else None


def set_preferred_camera(index: int) -> None:
    _prefs().set("camera_index", index)


def warm_up_authorization() -> None:
    """Resolve the macOS camera permission prompt on the main thread.

    OpenCV's AVFoundation backend requests camera access from the thread that
    owns the run loop; doing it from a worker thread fails with "can not spin
    main run loop from other thread". Opening (and immediately releasing) the
    default camera here settles the permission state once, so the background
    probe below runs already-authorized.
    """
    if sys.platform != "darwin":
        return
    try:
        cap = _open_capture(0)
        if cap is not None:
            cap.release()
    except Exception:  # noqa: BLE001 - never let this break the dialog
        pass


class CameraCapturer:
    """Stateful wrapper around a single ``cv2.VideoCapture``."""

    def __init__(self) -> None:
        self._cap: cv2.VideoCapture | None = None

    def open(self, index: int) -> bool:
        """Open ``index``; return ``False`` when it cannot be opened."""
        self.close()
        cap = _open_capture(index)
        if cap is None:
            return False
        self._cap = cap
        return True

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read_frame(self):
        """Return the next frame (BGR), or ``None`` when unavailable."""
        cap = self._cap
        if cap is None or not cap.isOpened():
            return None
        ok, frame = cap.read()
        return frame if ok and frame is not None else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def capture_frame(self, index: int) -> Path | None:
        """Capture one frame from ``index`` to a temp JPEG; return its path."""
        if not self.open(index):
            return None
        frame = self.read_frame()
        if frame is None:
            self.close()
            return None
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.close()
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                path = Path(tmp.name)
            image.save(path, "JPEG")
        except Exception:  # noqa: BLE001
            return None
        return path
