# Plan: Capture component photo from a camera

## Context

Today the only way to set a part's photo is **Add / change photo → pick an
existing file**. We want to also **take a photo on the spot** using a webcam /
camera, letting the user **choose which camera** when more than one is
connected, and store it as that component's photo.

## Findings

- Photo handling lives in `src/partiu/gui/views/detail.py`
  (`PartDetailView.add_photo()` → `Database.set_attachment(part_pk, "photo", path)`
  → `_load_photo()`). A captured frame can reuse this exact pipeline.
- `cv2` (OpenCV) is already available: it is a transitive dependency of
  `rapidocr` (verified `opencv_python` + `numpy`, `cv2.__version__` 5.0.0) and is
  already listed in the README build `--include-package=cv2`. `cv2.VideoCapture`
  gives cross-platform camera access + preview without a new dependency.
- macOS requires the `NSCameraUsageDescription` key in the app bundle
  `Info.plist`, or the app exits when it first touches the camera. Nuitka exposes
  this via `--macos-app-protected-resource="NSCameraUsageDescription:..."`.
- The GitHub Actions build (`release.yml`) currently omits the camera-related
  flags; the README manual macOS build already has `--include-package=cv2`.

## Approach

### 1. New camera UI module — `src/partiu/gui/camera.py`
- `list_cameras(max_index=5)` → probe `cv2.VideoCapture(i)` for `i` in
  `0..max_index`, keep the indices that open, release each, return
  `[(index, "Camera {index}"), ...]`.
- `CameraCaptureDialog(tk.Toplevel)`:
  - Combobox of cameras (populated by `list_cameras`) + **Refresh** button.
  - Live preview (Label/Canvas) updated by a `self.after(...)` loop: read frame,
    convert BGR→RGB, `PIL.Image` → `ImageTk.PhotoImage`, display; keep a strong
    reference to avoid GC. Flip horizontally for a natural self-view.
  - **Capture** → read current frame, save JPEG to a `tempfile` `.jpg`, store the
    path, release camera, close. Expose `.captured_path: Path | None`.
  - **Cancel** / window close → release camera, no path.
  - If no camera opens: show "No camera available" and disable Capture.
- Everything runs on the tkinter main thread (no worker thread needed).

### 2. Wire a "Take photo…" button in `detail.py`
- Add a button next to "Add / change photo" → `self.take_photo()`.
- `take_photo()`: open `CameraCaptureDialog(self)`, `wait_window`, read
  `captured_path`; if set, `db.set_attachment(part_pk, "photo", path)` then delete
  the temp file and `_load_photo()`. Reuses the existing save + refresh flow.

### 3. Build/packaging flags
- `README.md` manual macOS build: add
  `--macos-app-protected-resource="NSCameraUsageDescription:Camera access for capturing component photos."`.
- `.github/workflows/release.yml`: add the same `--macos-app-protected-resource`
  flag to the macOS build, and `--include-package=cv2` to both macOS and Windows
  builds (README already lists it).

## Files to modify

- `src/partiu/gui/camera.py` — **new** camera enumeration + capture dialog.
- `src/partiu/gui/views/detail.py` — "Take photo…" button + `take_photo()`.
- `README.md` — document camera capture; add macOS Info.plist build flag.
- `.github/workflows/release.yml` — macOS camera permission flag + `cv2` include.

## Reuse

- `Database.set_attachment(part_id, "photo", source_path)` (`db.py`) — same storage
  used by `add_photo()`; captured JPEG is saved as a temp file and handed to it.
- `PartDetailView._load_photo()` (`detail.py`) — refresh the thumbnail after capture.
- `PIL.Image` / `ImageTk` (already used in `detail.py`) — frame conversion/display.
- `cv2` (OpenCV) — already installed/bundled; no new dependency.

## Decisions (confirmed)

- Camera selector uses index labels (`Camera 0`, `Camera 1`, …) — no friendly
  device names.
- Interaction is a **live preview window with a Capture button**.

## Steps

- [ ] Add `src/partiu/gui/camera.py` (list_cameras + CameraCaptureDialog).
- [ ] Add "Take photo…" button and `take_photo()` in `detail.py`.
- [ ] Add macOS `NSCameraUsageDescription` flag + `cv2` include to build configs
      (`README.md`, `release.yml`).
- [ ] Document camera capture in `README.md`.

## Verification

- `poetry run partiu` → open a part's details → **Take photo…**:
  - Camera dropdown lists connected cameras; switching/Refresh re-detects.
  - Live preview shows; **Capture** saves the frame and the thumbnail updates
    (equivalent to "Add / change photo").
  - With two cameras, choose the second and confirm the correct one is used.
  - Closing the dialog without capturing leaves the existing photo unchanged.
  - No camera → clear "No camera available" message, no crash.
- macOS: on first use the system shows the Camera permission prompt; granting it
  enables preview; denying it shows the "No camera available" path.
- Packaging (optional): rebuild the macOS app and confirm the `.app` Info.plist
  contains `NSCameraUsageDescription`.
