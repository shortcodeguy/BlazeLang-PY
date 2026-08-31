import tempfile
import unittest
from pathlib import Path

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError
from blazelang.interpreter.interpreter import Interpreter
from blazelang.lexer.lexer import Lexer
from blazelang.parser.parser import Parser
from blazelang.stdlib.image import ImageLibrary


class ImageModuleTests(unittest.TestCase):
    def test_in_memory_creation_pixels_transforms_filters_and_drawing(self):
        image = ImageLibrary().Create(20, 10).Fill("#202020")
        self.assertEqual(image.GetPixel(0, 0), [32, 32, 32, 255])
        image.SetPixel(1, 2, 255, 0, 0, 128)
        self.assertEqual(image.GetPixel(1, 2), [255, 0, 0, 128])
        image.DrawLine(0, 0, 19, 9).DrawRect(2, 2, 5, 4).DrawCircle(10, 5, 3).DrawText(1, 1, "B")
        image.Resize(40, 20).Crop(0, 0, 20, 10).Rotate(90).FlipHorizontal().FlipVertical()
        image.Grayscale().Invert().Blur(1).Sharpen()
        self.assertEqual((image.width, image.height), (10, 20))

    def test_create_pixels_transforms_filters_and_save_open(self):
        with tempfile.TemporaryDirectory() as temp:
            library = ImageLibrary(temp)
            image = library.Create(20, 10)
            image.SetPixel(1, 2, 255, 0, 0, 128)
            self.assertEqual(image.GetPixel(1, 2), [255, 0, 0, 128])
            image.DrawLine(0, 0, 19, 9).DrawRect(2, 2, 5, 4).DrawCircle(10, 5, 3).DrawText(1, 1, "B")
            image.Resize(40, 20).Crop(0, 0, 20, 10).Rotate(90).FlipHorizontal().FlipVertical()
            image.Grayscale().Invert().Blur(1).Sharpen()
            self.assertTrue(image.Save("saved.png"))
            loaded = library.Open("saved.png")
            self.assertEqual((loaded.width, loaded.height), (10, 20))
            self.assertTrue((Path(temp) / "saved.png").is_file())

    def test_validation_errors_are_blazelang_errors(self):
        image = ImageLibrary().Create(4, 4)
        with self.assertRaises(BlazeRuntimeError): image.GetPixel(4, 0)
        with self.assertRaises(BlazeRuntimeError): image.SetPixel(0, 0, 256, 0, 0)
        with self.assertRaises(BlazeRuntimeError): image.Crop(3, 3, 2, 2)
        with self.assertRaises(BlazeRuntimeError): image.Save("invalid.gif")
        with self.assertRaises(BlazeRuntimeError): ImageLibrary().Open("does-not-exist.png")

    def test_supported_file_formats_and_alpha(self):
        with tempfile.TemporaryDirectory() as temp:
            library = ImageLibrary(temp)
            image = library.Create(2, 2).Fill("#10203040")
            for extension in ("png", "jpg", "bmp"):
                filename = f"image.{extension}"
                self.assertTrue(image.Save(filename))
                loaded = library.Open(filename)
                self.assertEqual((loaded.width, loaded.height), (2, 2))
            self.assertEqual(library.Open("image.png").GetPixel(0, 0), [16, 32, 48, 64])

    def test_interpreter_import_exposes_image_api(self):
        source = 'Import Image from "image"\nvar image = Image.Create(3, 2)\nvar width = image.width\nimage.SetPixel(0, 0, 1, 2, 3)\nvar pixel = image.GetPixel(0, 0)'
        interpreter = Interpreter(filename="<image-test>")
        interpreter.interpret(Parser(Lexer(source, "<image-test>").tokenize()).parse())
        self.assertEqual(interpreter.global_scope["width"]["value"], 3)
        self.assertEqual(interpreter.global_scope["pixel"]["value"], [1, 2, 3, 255])
