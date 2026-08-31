"""Native Pillow-backed image support for BlazeLang's ``image`` module."""

from pathlib import Path

try:
    from PIL import Image as PillowImage
    from PIL import ImageDraw, ImageFilter, ImageOps
except ImportError as error:  # pragma: no cover - exercised when packaging incorrectly
    raise ImportError("The Image module requires Pillow. Install dependencies from requirements.txt.") from error

from blazelang.errors.error_handler import RuntimeError as BlazeRuntimeError


_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".bmp": "BMP"}
_MAX_PIXELS = 100_000_000


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlazeRuntimeError(f"Image.{name} must be a whole number")
    try:
        integer = int(value)
    except (OverflowError, ValueError):
        raise BlazeRuntimeError(f"Image.{name} must be a whole number")
    if integer != value:
        raise BlazeRuntimeError(f"Image.{name} must be a whole number")
    return integer


def _channel(value, name):
    value = _integer(value, name)
    if not 0 <= value <= 255:
        raise BlazeRuntimeError(f"Image.{name} must be between 0 and 255")
    return value


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlazeRuntimeError(f"Image.{name} must be a number")
    return value


def _color(value, name="color"):
    if not isinstance(value, str):
        raise BlazeRuntimeError(f"Image.{name} must be a hex color such as '#RRGGBB'")
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) not in (6, 8):
        raise BlazeRuntimeError(f"Image.{name} must use #RRGGBB or #RRGGBBAA")
    try:
        channels = tuple(int(text[index:index + 2], 16) for index in range(0, len(text), 2))
    except ValueError:
        raise BlazeRuntimeError(f"Image.{name} must use #RRGGBB or #RRGGBBAA")
    return channels if len(channels) == 4 else channels + (255,)


class BlazeImage:
    """An RGBA image. Operations mutate it and return itself for chaining."""

    def __init__(self, image, base_dir=None):
        self._image = image.convert("RGBA")
        self._base_dir = Path(base_dir) if base_dir else Path.cwd()

    @property
    def width(self):
        return self._image.width

    @property
    def height(self):
        return self._image.height

    def _point(self, x, y):
        x, y = _integer(x, "x"), _integer(y, "y")
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise BlazeRuntimeError(f"Image coordinates ({x}, {y}) are outside the image bounds")
        return x, y

    def Resize(self, width, height):
        width, height = _integer(width, "Resize width"), _integer(height, "Resize height")
        if width <= 0 or height <= 0:
            raise BlazeRuntimeError("Image.Resize dimensions must be greater than 0")
        if width * height > _MAX_PIXELS:
            raise BlazeRuntimeError("Image.Resize dimensions are too large")
        self._image = self._image.resize((width, height), PillowImage.Resampling.LANCZOS)
        return self

    def Crop(self, x, y, width, height):
        x, y = _integer(x, "Crop x"), _integer(y, "Crop y")
        width, height = _integer(width, "Crop width"), _integer(height, "Crop height")
        if width <= 0 or height <= 0:
            raise BlazeRuntimeError("Image.Crop dimensions must be greater than 0")
        if x < 0 or y < 0 or x + width > self.width or y + height > self.height:
            raise BlazeRuntimeError("Image.Crop region is outside the image bounds")
        self._image = self._image.crop((x, y, x + width, y + height))
        return self

    def Rotate(self, degrees):
        degrees = _number(degrees, "Rotate degrees")
        self._image = self._image.rotate(degrees, expand=True, resample=PillowImage.Resampling.BICUBIC)
        return self

    def FlipHorizontal(self):
        self._image = ImageOps.mirror(self._image)
        return self

    def FlipVertical(self):
        self._image = ImageOps.flip(self._image)
        return self

    def Grayscale(self):
        alpha = self._image.getchannel("A")
        self._image = ImageOps.grayscale(self._image).convert("RGBA")
        self._image.putalpha(alpha)
        return self

    def Invert(self):
        alpha = self._image.getchannel("A")
        self._image = ImageOps.invert(self._image.convert("RGB")).convert("RGBA")
        self._image.putalpha(alpha)
        return self

    def Blur(self, radius):
        radius = _number(radius, "Blur radius")
        if radius < 0:
            raise BlazeRuntimeError("Image.Blur radius cannot be negative")
        self._image = self._image.filter(ImageFilter.GaussianBlur(radius))
        return self

    def Sharpen(self):
        self._image = self._image.filter(ImageFilter.SHARPEN)
        return self

    def Fill(self, color):
        self._image.paste(_color(color, "Fill color"), (0, 0, self.width, self.height))
        return self

    def SetPixel(self, x, y, red, green, blue, alpha=255):
        x, y = self._point(x, y)
        self._image.putpixel((x, y), (_channel(red, "red"), _channel(green, "green"), _channel(blue, "blue"), _channel(alpha, "alpha")))
        return self

    def GetPixel(self, x, y):
        x, y = self._point(x, y)
        return list(self._image.getpixel((x, y)))

    def DrawLine(self, x1, y1, x2, y2, color="#000000", width=1):
        points = (self._point(x1, y1), self._point(x2, y2))
        width = _integer(width, "DrawLine width")
        if width <= 0:
            raise BlazeRuntimeError("Image.DrawLine width must be greater than 0")
        ImageDraw.Draw(self._image).line(points, fill=_color(color, "DrawLine color"), width=width)
        return self

    def DrawRect(self, x, y, width, height, color="#000000", fill=False):
        x, y = _integer(x, "DrawRect x"), _integer(y, "DrawRect y")
        width, height = _integer(width, "DrawRect width"), _integer(height, "DrawRect height")
        if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > self.width or y + height > self.height:
            raise BlazeRuntimeError("Image.DrawRect region is outside the image bounds")
        if not isinstance(fill, bool):
            raise BlazeRuntimeError("Image.DrawRect fill must be a boolean")
        draw = ImageDraw.Draw(self._image)
        box = (x, y, x + width - 1, y + height - 1)
        draw.rectangle(box, fill=_color(color, "DrawRect color") if fill else None, outline=_color(color, "DrawRect color"))
        return self

    def DrawCircle(self, x, y, radius, color="#000000", fill=False):
        x, y = _integer(x, "DrawCircle x"), _integer(y, "DrawCircle y")
        radius = _integer(radius, "DrawCircle radius")
        if radius < 0 or x - radius < 0 or y - radius < 0 or x + radius >= self.width or y + radius >= self.height:
            raise BlazeRuntimeError("Image.DrawCircle region is outside the image bounds")
        if not isinstance(fill, bool):
            raise BlazeRuntimeError("Image.DrawCircle fill must be a boolean")
        color = _color(color, "DrawCircle color")
        ImageDraw.Draw(self._image).ellipse((x - radius, y - radius, x + radius, y + radius), fill=color if fill else None, outline=color)
        return self

    def DrawText(self, x, y, text, color="#000000"):
        x, y = self._point(x, y)
        if not isinstance(text, str):
            raise BlazeRuntimeError("Image.DrawText text must be a string")
        ImageDraw.Draw(self._image).text((x, y), text, fill=_color(color, "DrawText color"))
        return self

    def Save(self, path):
        path = self._resolve(path, "Save path")
        image_format = _FORMATS.get(path.suffix.lower())
        if not image_format:
            raise BlazeRuntimeError("Image.Save supports PNG, JPG, JPEG, and BMP files")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            image = self._image.convert("RGB") if image_format == "JPEG" else self._image
            image.save(path, format=image_format)
        except (OSError, ValueError) as error:
            raise BlazeRuntimeError(f"Image.Save failed: {error}")
        return True

    def _resolve(self, path, name):
        if not isinstance(path, str) or not path:
            raise BlazeRuntimeError(f"Image.{name} must be a non-empty path string")
        target = Path(path)
        return target if target.is_absolute() else self._base_dir / target


class ImageLibrary:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()

    def _path(self, path, name):
        if not isinstance(path, str) or not path:
            raise BlazeRuntimeError(f"Image.{name} path must be a non-empty string")
        target = Path(path)
        return target if target.is_absolute() else self.base_dir / target

    def Create(self, width, height):
        width, height = _integer(width, "Create width"), _integer(height, "Create height")
        if width <= 0 or height <= 0:
            raise BlazeRuntimeError("Image.Create dimensions must be greater than 0")
        if width * height > _MAX_PIXELS:
            raise BlazeRuntimeError("Image.Create dimensions are too large")
        return BlazeImage(PillowImage.new("RGBA", (width, height), (0, 0, 0, 0)), self.base_dir)

    def Open(self, path):
        target = self._path(path, "Open")
        if target.suffix.lower() not in _FORMATS:
            raise BlazeRuntimeError("Image.Open supports PNG, JPG, JPEG, and BMP files")
        try:
            with PillowImage.open(target) as image:
                image.load()
                return BlazeImage(image.copy(), self.base_dir)
        except FileNotFoundError:
            raise BlazeRuntimeError(f"Image.Open could not find '{path}'")
        except (OSError, ValueError) as error:
            raise BlazeRuntimeError(f"Image.Open failed: {error}")


def create_image_module(base_dir=None):
    library = ImageLibrary(base_dir)
    return {"Open": library.Open, "Create": library.Create}
