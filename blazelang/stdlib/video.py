"""Native OpenCV-backed video support for BlazeLang's ``video`` module."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import cv2
except ImportError as error:  # pragma: no cover
    raise ImportError("The Video module requires opencv-python. Install dependencies from requirements.txt.") from error

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


_SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm", ".flv"}


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlazeRuntimeError(f"Video.{name} must be a number")
    return float(value)


class BlazeVideo:
    """A Video object backing playback decoding, metadata, seeking, and GUI listener notification."""

    def __init__(self, path: Any, base_dir: Optional[Path] = None):
        self._cap: Optional[cv2.VideoCapture] = None
        self._listeners: List[Callable[[Any], None]] = []
        self._tk_widget: Optional[Any] = None
        self._playing = False

        if not isinstance(path, str) or not path.strip():
            raise BlazeRuntimeError("Video.Load path must be a non-empty string")

        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        target = Path(path)
        if target.is_absolute():
            resolved = target
        else:
            resolved = self.base_dir / target
            if not resolved.is_file() and (Path.cwd() / target).is_file():
                resolved = Path.cwd() / target

        if not resolved.is_file():
            raise BlazeRuntimeError(f"Video.Load could not find '{path}'")

        cap = cv2.VideoCapture(str(resolved))
        if not cap.isOpened():
            raise BlazeRuntimeError(f"Video.Load failed to open or read video file '{path}'")

        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if w <= 0 or h <= 0 or frame_count <= 0:
            cap.release()
            raise BlazeRuntimeError(f"Video.Load encountered corrupted or unreadable video file '{path}'")

        duration = (frame_count / fps) if fps > 0 else 0.0

        self._cap = cap
        self._path = resolved
        self._raw_path = path
        self._width = w
        self._height = h
        self._fps = fps if fps > 0 else 30.0
        self._frame_count = frame_count
        self._duration = round(duration, 3)
        self._position = 0.0
        self._scheduled = False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def duration(self) -> float:
        return self._duration

    def Width(self) -> int:
        return self._width

    def Height(self) -> int:
        return self._height

    def Duration(self) -> float:
        return self._duration

    def AddListener(self, callback: Callable[[Any], None]):
        if callback not in self._listeners:
            self._listeners.append(callback)
            # Instantly push current initial frame if available
            initial_frame = self.GetFrame()
            if initial_frame is not None:
                try:
                    callback(initial_frame)
                except Exception:
                    pass

    def RemoveListener(self, callback: Callable[[Any], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def NotifyListeners(self, frame_pil: Any):
        for cb in list(self._listeners):
            try:
                cb(frame_pil)
            except Exception:
                pass

    def _bind_widget(self, tk_widget: Any):
        self._tk_widget = tk_widget
        if self._playing:
            self._schedule_tick()

    def _schedule_tick(self):
        if self._playing and self._tk_widget is not None and not self._scheduled:
            self._scheduled = True
            delay = max(1, int(1000.0 / self._fps))
            try:
                self._tk_widget.after(delay, self._tick)
            except Exception:
                self._scheduled = False

    def _tick(self):
        self._scheduled = False
        if not self._playing or self._cap is None:
            return

        frame_pil = self.GetFrame()
        if frame_pil is None:
            self._playing = False
            self.Seek(0.0)
            return

        self.NotifyListeners(frame_pil)

        if self._playing and self._tk_widget is not None:
            self._schedule_tick()

    def Play(self) -> "BlazeVideo":
        self._playing = True
        self._schedule_tick()
        return self

    def Pause(self) -> "BlazeVideo":
        self._playing = False
        return self

    def Stop(self) -> "BlazeVideo":
        self._playing = False
        return self.Seek(0.0)

    def Seek(self, seconds: Any) -> "BlazeVideo":
        pos = _number(seconds, "Seek position")
        if pos < 0 or (self._duration > 0 and pos > self._duration):
            raise BlazeRuntimeError(f"Video.Seek position must be between 0 and {self._duration} seconds")

        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, pos * 1000.0)
            self._position = pos
            frame_pil = self.GetFrame()
            if frame_pil is not None:
                self.NotifyListeners(frame_pil)
        return self

    def IsPlaying(self) -> bool:
        return self._playing

    def GetPosition(self) -> float:
        if self._playing and self._cap is not None:
            current_msec = self._cap.get(cv2.CAP_PROP_POS_MSEC)
            if current_msec > 0:
                self._position = round(current_msec / 1000.0, 3)
        return self._position

    def GetFrame(self) -> Optional[Any]:
        """Read and return current frame converted to PIL Image."""
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        if not ret:
            return None
        from PIL import Image as PillowImage
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return PillowImage.fromarray(frame_rgb)

    def Close(self) -> None:
        self._playing = False
        if hasattr(self, "_listeners") and self._listeners is not None:
            self._listeners.clear()
        self._tk_widget = None
        if hasattr(self, "_cap") and self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def __del__(self):
        self.Close()


class VideoLibrary:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    def Load(self, path: Any) -> BlazeVideo:
        return BlazeVideo(path, self.base_dir)

    def Open(self, path: Any) -> BlazeVideo:
        return self.Load(path)


def create_video_module(base_dir: Optional[Path] = None) -> Dict[str, Any]:
    library = VideoLibrary(base_dir)
    return {
        "Load": library.Load,
        "Open": library.Open,
    }
