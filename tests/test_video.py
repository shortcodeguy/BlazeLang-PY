import tempfile
import unittest
from pathlib import Path

try:
    import cv2
    import numpy as np
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.video import VideoLibrary


def _create_sample_video(path: str, width: int = 100, height: int = 100, fps: float = 30.0, duration_sec: float = 1.5):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    total_frames = int(fps * duration_sec)
    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (i * 5 % 255, 128, 255 - (i * 5 % 255))
        out.write(frame)
    out.release()


@unittest.skipUnless(_HAS_CV2, "opencv-python not available")
class VideoModuleTests(unittest.TestCase):

    def test_load_metadata_and_playback_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            video_path = str(Path(temp) / "test_sample.mp4")
            _create_sample_video(video_path, width=120, height=80, fps=30.0, duration_sec=1.5)

            library = VideoLibrary(temp)
            video = library.Load(video_path)

            self.assertEqual(video.Width(), 120)
            self.assertEqual(video.Height(), 80)
            self.assertGreater(video.Duration(), 1.0)
            self.assertEqual(video.width, 120)
            self.assertEqual(video.height, 80)

            self.assertFalse(video.IsPlaying())
            video.Play()
            self.assertTrue(video.IsPlaying())
            video.Pause()
            self.assertFalse(video.IsPlaying())

            video.Seek(0.5)
            self.assertAlmostEqual(video.GetPosition(), 0.5, delta=0.2)

            video.Stop()
            self.assertFalse(video.IsPlaying())
            self.assertAlmostEqual(video.GetPosition(), 0.0, delta=0.2)

            video.Close()

    def test_validation_errors(self):
        library = VideoLibrary()
        with self.assertRaises(BlazeRuntimeError):
            library.Load("non_existent_video_12345.mp4")

        with tempfile.TemporaryDirectory() as temp:
            dummy_file = str(Path(temp) / "corrupt.mp4")
            with open(dummy_file, "w") as f:
                f.write("corrupted data")
            with self.assertRaises(BlazeRuntimeError):
                library.Load(dummy_file)

        with tempfile.TemporaryDirectory() as temp:
            video_path = str(Path(temp) / "test_valid.mp4")
            _create_sample_video(video_path, width=64, height=64, fps=30.0, duration_sec=1.0)
            v = library.Load(video_path)
            with self.assertRaises(BlazeRuntimeError):
                v.Seek(-1.0)
            with self.assertRaises(BlazeRuntimeError):
                v.Seek(100.0)
            with self.assertRaises(BlazeRuntimeError):
                v.Seek("invalid")
            v.Close()

    def test_interpreter_import_exposes_video_api(self):
        with tempfile.TemporaryDirectory() as temp:
            video_path = str(Path(temp) / "blaze_vid.mp4")
            _create_sample_video(video_path, width=200, height=150, fps=25.0, duration_sec=1.0)

            escaped_path = video_path.replace("\\", "\\\\")

            source = f'''
Import Video from "video"
var v = Video.Load("{escaped_path}")
var w = v.Width()
var h = v.Height()
var dur = v.Duration()
v.Play()
v.Pause()
v.Seek(0.2)
v.Stop()
'''
            interpreter = Interpreter(filename="<video-test>")
            interpreter.interpret(Parser(Lexer(source, "<video-test>").tokenize()).parse())
            self.assertEqual(interpreter.global_scope["w"]["value"], 200)
            self.assertEqual(interpreter.global_scope["h"]["value"], 150)

            video_obj = interpreter.global_scope["v"]["value"]
            if hasattr(video_obj, "Close"):
                video_obj.Close()
