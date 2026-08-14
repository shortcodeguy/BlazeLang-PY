"""
BlazeLang GUI Module
Native desktop GUI for BlazeLang using tkinter.

Import:
    Import GUI from "gui"

Main API:
    GUI.Create(title, width, height)
    GUI.Style({...})

    GUI.Label(...)
    GUI.Button(...)
    GUI.Input(...)
    GUI.PasswordInput(...)
    GUI.Checkbox(...)
    GUI.TextArea(...)
    GUI.Panel(...)
    GUI.Row(...)
    GUI.Column(...)

Styling:
    component.Style({...})
    component.SetStyle({...})
    component.UseStyle(style)

Example:

    var app = GUI.Create("My App", 500, 400)

    app.SetStyle({
        background: "#111827"
    })

    var button = GUI.Button("Click")

    button.SetStyle({
        background: "#2563eb",
        foreground: "#ffffff",
        font: 20,
        width: 8,
        height: 2,
        padding: 10,
        cursor: "hand2"
    })

    app.Add(button)
    app.Run()

The styling system is CSS-inspired but maps to native tkinter options.
"""


import os
import sys
import ctypes
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional


from blazelang.errors.error_handler import (
    RuntimeError as BlazeRuntimeError,
    TypeError as BlazeTypeError,
    ValueError as BlazeValueError,
)


# ============================================================
# Windows / Resource Helpers
# ============================================================

def _set_windows_app_identity():
    """
    Give Windows a stable AppUserModelID.

    This helps Windows associate the GUI with BlazeLang instead
    of Python when running from the interpreter.
    """

    if sys.platform != "win32":
        return

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ShortCodeGuy.BlazeLang.GUI"
        )
    except Exception:
        pass


def _get_base_directory() -> str:
    """
    Resolve the project/runtime directory.

    Supports:
        python main.py
        PyInstaller
        frozen executables
    """

    if getattr(sys, "frozen", False):
        return getattr(
            sys,
            "_MEIPASS",
            os.path.dirname(sys.executable),
        )

    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
        )
    )


def _get_gui_icon_path() -> Optional[str]:
    """
    Search for the BlazeLang icon.
    """

    base_dir = _get_base_directory()

    candidates = [
        os.path.join(
            base_dir,
            "blaze.ico",
        ),

        os.path.join(
            base_dir,
            "assets",
            "blaze.ico",
        ),

        os.path.join(
            base_dir,
            "blazelang",
            "assets",
            "blaze.ico",
        ),

        os.path.join(
            os.path.dirname(__file__),
            "blaze.ico",
        ),

        os.path.join(
            os.path.dirname(__file__),
            "assets",
            "blaze.ico",
        ),
    ]

    seen = set()

    for path in candidates:

        path = os.path.abspath(path)

        if path in seen:
            continue

        seen.add(path)

        if os.path.isfile(path):
            return path

    return None


# ============================================================
# Helpers
# ============================================================

def _is_blaze_function(value: Any) -> bool:
    return (
        hasattr(value, "__call__")
        and hasattr(value, "parameters")
    )


def _invoke_callback(
    interpreter,
    callback: Any,
    args: List[Any],
):

    if _is_blaze_function(callback):

        return callback(
            interpreter,
            args,
        )

    if callable(callback):

        return callback(*args)

    raise BlazeTypeError(
        "Expected a callback function, "
        f"got {type(callback).__name__}"
    )


def _normalize_style(style: Any) -> Dict[str, Any]:
    """
    Convert BlazeLang object/dictionary values into
    a Python dictionary.
    """

    if isinstance(style, dict):
        return dict(style)

    if hasattr(style, "properties"):

        properties = getattr(
            style,
            "properties",
        )

        if isinstance(properties, dict):
            return dict(properties)

    if hasattr(style, "__dict__"):

        values = dict(
            style.__dict__
        )

        if "values" in values:
            stored = values["values"]

            if isinstance(stored, dict):
                return dict(stored)

        return values

    raise BlazeTypeError(
        "GUI style expects an object/dictionary"
    )


def _safe_config(
    widget,
    option,
    value,
):
    """
    Configure a tkinter widget without allowing one
    unsupported option to break the whole GUI.
    """

    if value is None:
        return

    try:
        widget.configure(
            **{
                option: value
            }
        )
    except (
        tk.TclError,
        TypeError,
        ValueError,
    ):
        pass


def _parse_font(style: Dict[str, Any]):
    """
    Build a tkinter font from the CSS-inspired style.

    Supported:

        font: 20

        font: "Segoe UI 20 bold"

        font_family: "Segoe UI"
        font_size: 20
        bold: true
        italic: true
    """

    font_value = style.get("font")

    family = style.get(
        "font_family",
        "Segoe UI",
    )

    size = style.get(
        "font_size",
        12,
    )

    bold = style.get(
        "bold",
        False,
    )

    italic = style.get(
        "italic",
        False,
    )

    if isinstance(
        font_value,
        (int, float),
    ):
        size = int(font_value)

    elif isinstance(
        font_value,
        str,
    ):
        return font_value

    elif isinstance(
        font_value,
        (tuple, list),
    ):
        return tuple(font_value)

    try:
        size = int(size)
    except Exception:
        size = 12

    weight = (
        "bold"
        if bold
        else "normal"
    )

    slant = (
        "italic"
        if italic
        else "roman"
    )

    return (
        str(family),
        size,
        weight,
        slant,
    )


class _DestroyedError(BlazeRuntimeError):

    def __init__(self, what: str):

        super().__init__(
            f"Cannot operate on '{what}': "
            "the GUI window has been closed",

            code="BLZ9001",

            hint=(
                "Create a new window with GUI.Create(...) "
                "before using GUI components again."
            ),
        )


# ============================================================
# GUI Style
# ============================================================

class GUIStyle:
    """
    Reusable GUI style.

    Example:

        var primary = GUI.Style({
            background: "#2563eb",
            color: "#ffffff",
            font: 18
        })
    """

    def __init__(
        self,
        values: Any = None,
    ):

        if values is None:
            self.values = {}

        else:
            self.values = _normalize_style(
                values
            )

    def Get(
        self,
        key: str,
        default=None,
    ):

        return self.values.get(
            key,
            default,
        )

    def Set(
        self,
        key: str,
        value: Any,
    ):

        self.values[key] = value

        return self

    def Update(
        self,
        values: Any,
    ):

        self.values.update(
            _normalize_style(values)
        )

        return self


# ============================================================
# Component Base
# ============================================================

class GUIComponent:

    kind = "Component"

    def __init__(self):

        self._widget: Optional[
            tk.Widget
        ] = None

        self._window: Optional[
            "Window"
        ] = None

        self._destroyed = False

        self._visible = True

        self._enabled = True

        self._style: Dict[
            str,
            Any
        ] = {}

    def _ensure_alive(self):

        if self._destroyed:

            raise _DestroyedError(
                self.kind
            )

    # --------------------------------------------------------
    # Styling
    # --------------------------------------------------------

    def Style(
        self,
        style: Any,
    ):

        self._ensure_alive()

        self._style.update(
            _normalize_style(style)
        )

        if self._widget is not None:

            self._apply_style()

        return self

    def SetStyle(
        self,
        style: Any,
    ):
        """
        Alias for Style().

        This is the main developer-facing API.
        """

        return self.Style(
            style
        )

    def UseStyle(
        self,
        style: Any,
    ):

        self._ensure_alive()

        if isinstance(
            style,
            GUIStyle,
        ):

            self._style.update(
                style.values
            )

        else:

            self._style.update(
                _normalize_style(style)
            )

        if self._widget is not None:

            self._apply_style()

        return self

    def GetStyle(
        self,
        key: str,
        default=None,
    ):

        return self._style.get(
            key,
            default,
        )

    def SetStyleValue(
        self,
        key: str,
        value: Any,
    ):

        self._ensure_alive()

        self._style[key] = value

        if self._widget is not None:

            self._apply_style()

        return self

    # --------------------------------------------------------
    # Visibility
    # --------------------------------------------------------

    def Show(self):

        self._ensure_alive()

        self._visible = True

        if self._widget is not None:

            try:
                self._widget.pack()
            except tk.TclError:
                pass

        return self

    def Hide(self):

        self._ensure_alive()

        self._visible = False

        if self._widget is not None:

            try:
                self._widget.pack_forget()
            except tk.TclError:
                pass

        return self

    # --------------------------------------------------------
    # Enable / Disable
    # --------------------------------------------------------

    def Enable(self):

        self._ensure_alive()

        self._enabled = True

        if self._widget is not None:

            _safe_config(
                self._widget,
                "state",
                "normal",
            )

        return self

    def Disable(self):

        self._ensure_alive()

        self._enabled = False

        if self._widget is not None:

            _safe_config(
                self._widget,
                "state",
                "disabled",
            )

        return self

    # --------------------------------------------------------
    # Geometry helpers
    # --------------------------------------------------------

    def SetWidth(
        self,
        width: int,
    ):

        self._style["width"] = width

        if self._widget is not None:

            _safe_config(
                self._widget,
                "width",
                int(width),
            )

        return self

    def SetHeight(
        self,
        height: int,
    ):

        self._style["height"] = height

        if self._widget is not None:

            _safe_config(
                self._widget,
                "height",
                int(height),
            )

        return self

    def SetPadding(
        self,
        padding: Any,
    ):

        self._style["padding"] = padding

        if self._widget is not None:

            self._apply_style()

        return self

    # --------------------------------------------------------
    # Build
    # --------------------------------------------------------

    def _build(
        self,
        parent: tk.Widget,
    ) -> tk.Widget:

        raise NotImplementedError

    def _realize(
        self,
        parent: tk.Widget,
    ) -> tk.Widget:

        self._ensure_alive()

        if self._widget is None:

            self._widget = self._build(
                parent
            )

            self._apply_style()

        return self._widget

    # --------------------------------------------------------
    # Styling engine
    # --------------------------------------------------------

    def _apply_style(self):

        if self._widget is None:
            return

        style = self._style

        background = style.get(
            "background",
            style.get(
                "bg"
            ),
        )

        foreground = style.get(
            "foreground",
            style.get(
                "color"
            ),
        )

        font = _parse_font(
            style
        )

        width = style.get(
            "width"
        )

        height = style.get(
            "height"
        )

        cursor = style.get(
            "cursor"
        )

        relief = style.get(
            "relief"
        )

        border = style.get(
            "border",
            style.get(
                "borderwidth"
            ),
        )

        highlight = style.get(
            "highlight"
        )

        active_background = style.get(
            "active_background",
            style.get(
                "hover_background"
            ),
        )

        active_foreground = style.get(
            "active_foreground",
            style.get(
                "hover_color"
            ),
        )

        padding = style.get(
            "padding"
        )

        padx = style.get(
            "padx",
            padding,
        )

        pady = style.get(
            "pady",
            padding,
        )

        _safe_config(
            self._widget,
            "background",
            background,
        )

        _safe_config(
            self._widget,
            "bg",
            background,
        )

        _safe_config(
            self._widget,
            "foreground",
            foreground,
        )

        _safe_config(
            self._widget,
            "fg",
            foreground,
        )

        _safe_config(
            self._widget,
            "font",
            font,
        )

        if width is not None:

            _safe_config(
                self._widget,
                "width",
                int(width),
            )

        if height is not None:

            _safe_config(
                self._widget,
                "height",
                int(height),
            )

        _safe_config(
            self._widget,
            "cursor",
            cursor,
        )

        _safe_config(
            self._widget,
            "relief",
            relief,
        )

        _safe_config(
            self._widget,
            "borderwidth",
            border,
        )

        _safe_config(
            self._widget,
            "highlightbackground",
            highlight,
        )

        _safe_config(
            self._widget,
            "activebackground",
            active_background,
        )

        _safe_config(
            self._widget,
            "activeforeground",
            active_foreground,
        )

        # Internal geometry
        if padx is not None:

            try:

                self._widget.pack_configure(
                    padx=padx
                )

            except tk.TclError:
                pass

        if pady is not None:

            try:

                self._widget.pack_configure(
                    pady=pady
                )

            except tk.TclError:
                pass


# ============================================================
# Label
# ============================================================

class Label(GUIComponent):

    kind = "Label"

    def __init__(
        self,
        text: str = "",
    ):

        super().__init__()

        if not isinstance(
            text,
            str,
        ):

            raise BlazeTypeError(
                "GUI.Label(text) expects a string, "
                f"got {type(text).__name__}"
            )

        self.text = text

    def _build(
        self,
        parent,
    ):

        widget = tk.Label(
            parent,
            text=self.text,
            anchor="w",
            bd=0,
        )

        widget.pack(
            anchor="w",
            fill="x",
            padx=4,
            pady=2,
        )

        return widget

    def SetText(
        self,
        text: str,
    ):

        self._ensure_alive()

        if not isinstance(
            text,
            str,
        ):

            raise BlazeTypeError(
                "Label.SetText(text) expects a string"
            )

        self.text = text

        if self._widget is not None:

            self._widget.config(
                text=text
            )

        return self


# ============================================================
# Button
# ============================================================

class Button(GUIComponent):

    kind = "Button"

    def __init__(
        self,
        text: str = "",
    ):

        super().__init__()

        if not isinstance(
            text,
            str,
        ):

            raise BlazeTypeError(
                "GUI.Button(text) expects a string"
            )

        self.text = text

        self._callback = None
        self._interpreter = None

    def _build(
        self,
        parent,
    ):

        widget = tk.Button(
            parent,
            text=self.text,
            command=self._on_click,
            relief="flat",
            bd=0,
            cursor="hand2",
            takefocus=True,
        )

        widget.pack(
            side="left",
            fill="both",
            expand=True,
            padx=4,
            pady=4,
        )

        return widget

    def SetText(
        self,
        text: str,
    ):

        self._ensure_alive()

        if not isinstance(
            text,
            str,
        ):

            raise BlazeTypeError(
                "Button.SetText(text) expects a string"
            )

        self.text = text

        if self._widget is not None:

            self._widget.config(
                text=text
            )

        return self

    def OnClick(
        self,
        callback: Any,
    ):

        self._ensure_alive()

        if not (
            _is_blaze_function(callback)
            or callable(callback)
        ):

            raise BlazeTypeError(
                "Button.OnClick(function) "
                "expects a callable function"
            )

        self._callback = callback

        return self

    def _on_click(self):

        if self._callback is None:
            return

        if self._interpreter is None:
            return

        try:

            _invoke_callback(
                self._interpreter,
                self._callback,
                [],
            )

        except BlazeRuntimeError:

            raise

        except Exception as error:

            print(
                "[BlazeLang GUI] "
                f"Button callback error: {error}"
            )


# ============================================================
# Text Input
# ============================================================

class _TextInput(GUIComponent):

    kind = "Input"
    _show_char = None

    def __init__(
        self,
        placeholder: str = "",
    ):

        super().__init__()

        if not isinstance(
            placeholder,
            str,
        ):

            raise BlazeTypeError(
                f"GUI.{self.kind}(placeholder) "
                "expects a string"
            )

        self.placeholder = placeholder

        self._var: Optional[
            tk.StringVar
        ] = None

        self._callback = None
        self._interpreter = None

        self._changing = False

    def _build(
        self,
        parent,
    ):

        self._var = tk.StringVar()

        kwargs = {}

        if self._show_char is not None:

            kwargs["show"] = (
                self._show_char
            )

        widget = tk.Entry(
            parent,
            textvariable=self._var,
            relief="flat",
            bd=0,
            **kwargs,
        )

        widget.pack(
            anchor="w",
            fill="x",
            padx=4,
            pady=4,
        )

        self._var.trace_add(
            "write",
            lambda *_:
                self._on_change(),
        )

        return widget

    def _on_change(self):

        if self._changing:
            return

        if self._callback is None:
            return

        if self._interpreter is None:
            return

        try:

            _invoke_callback(
                self._interpreter,
                self._callback,
                [self.GetValue()],
            )

        except Exception as error:

            print(
                "[BlazeLang GUI] "
                f"Input callback error: {error}"
            )

    def OnChange(
        self,
        callback: Any,
    ):

        self._ensure_alive()

        if not (
            _is_blaze_function(callback)
            or callable(callback)
        ):

            raise BlazeTypeError(
                f"{self.kind}.OnChange(function) "
                "expects a callable function"
            )

        self._callback = callback

        return self

    def GetValue(self) -> str:

        self._ensure_alive()

        if self._var is not None:

            return self._var.get()

        return ""

    def SetValue(
        self,
        value: str,
    ):

        self._ensure_alive()

        if not isinstance(
            value,
            str,
        ):

            raise BlazeTypeError(
                f"{self.kind}.SetValue(value) "
                "expects a string"
            )

        if self._var is not None:

            self._changing = True

            try:

                self._var.set(
                    value
                )

            finally:

                self._changing = False

        return self


class Input(_TextInput):

    kind = "Input"
    _show_char = None


class PasswordInput(_TextInput):

    kind = "PasswordInput"
    _show_char = "*"


# ============================================================
# Checkbox
# ============================================================

class Checkbox(GUIComponent):

    kind = "Checkbox"

    def __init__(
        self,
        text: str = "",
    ):

        super().__init__()

        if not isinstance(
            text,
            str,
        ):

            raise BlazeTypeError(
                "GUI.Checkbox(text) expects a string"
            )

        self.text = text

        self._var: Optional[
            tk.BooleanVar
        ] = None

        self._callback = None
        self._interpreter = None

    def _build(
        self,
        parent,
    ):

        self._var = tk.BooleanVar(
            value=False
        )

        widget = tk.Checkbutton(
            parent,
            text=self.text,
            variable=self._var,
            command=self._on_change,
            anchor="w",
            bd=0,
            highlightthickness=0,
        )

        widget.pack(
            anchor="w",
            fill="x",
            padx=4,
            pady=3,
        )

        return widget

    def SetText(
        self,
        text: str,
    ):

        self._ensure_alive()

        self.text = text

        if self._widget is not None:

            self._widget.config(
                text=text
            )

        return self

    def OnChange(
        self,
        callback: Any,
    ):

        self._ensure_alive()

        if not (
            _is_blaze_function(callback)
            or callable(callback)
        ):

            raise BlazeTypeError(
                "Checkbox.OnChange(function) "
                "expects a callable function"
            )

        self._callback = callback

        return self

    def IsChecked(self) -> bool:

        self._ensure_alive()

        if self._var is not None:

            return bool(
                self._var.get()
            )

        return False

    def SetChecked(
        self,
        value: bool,
    ):

        self._ensure_alive()

        if self._var is not None:

            self._var.set(
                bool(value)
            )

        return self

    def _on_change(self):

        if self._callback is None:
            return

        if self._interpreter is None:
            return

        try:

            _invoke_callback(
                self._interpreter,
                self._callback,
                [self.IsChecked()],
            )

        except Exception as error:

            print(
                "[BlazeLang GUI] "
                f"Checkbox callback error: {error}"
            )


# ============================================================
# TextArea
# ============================================================

class TextArea(GUIComponent):

    kind = "TextArea"

    def __init__(
        self,
        placeholder: str = "",
    ):

        super().__init__()

        if not isinstance(
            placeholder,
            str,
        ):

            raise BlazeTypeError(
                "GUI.TextArea(placeholder) "
                "expects a string"
            )

        self.placeholder = placeholder

    def _build(
        self,
        parent,
    ):

        widget = tk.Text(
            parent,
            height=6,
            width=40,
            relief="flat",
            bd=0,
            wrap="word",
        )

        widget.pack(
            anchor="w",
            fill="both",
            expand=True,
            padx=4,
            pady=4,
        )

        return widget

    def GetValue(self) -> str:

        self._ensure_alive()

        if self._widget is not None:

            return self._widget.get(
                "1.0",
                "end-1c",
            )

        return ""

    def SetValue(
        self,
        value: str,
    ):

        self._ensure_alive()

        if not isinstance(
            value,
            str,
        ):

            raise BlazeTypeError(
                "TextArea.SetValue(value) "
                "expects a string"
            )

        if self._widget is not None:

            self._widget.delete(
                "1.0",
                "end",
            )

            self._widget.insert(
                "1.0",
                value,
            )

        return self

    def Clear(self):

        return self.SetValue("")


# ============================================================
# Containers
# ============================================================

class Container(GUIComponent):

    kind = "Container"

    _pack_side = "top"

    def __init__(self):

        super().__init__()

        self.children: List[
            GUIComponent
        ] = []

    def Add(
        self,
        component: Any,
    ):

        self._ensure_alive()

        if not isinstance(
            component,
            GUIComponent,
        ):

            raise BlazeTypeError(
                f"{self.kind}.Add(component) "
                "expects a GUI component"
            )

        self.children.append(
            component
        )

        component._window = (
            self._window
        )

        if self._widget is not None:

            self._attach_child(
                component
            )

        return self

    def _build(
        self,
        parent,
    ):

        background = self._style.get(
            "background",
            self._style.get(
                "bg"
            ),
        )

        kwargs = {
            "bd": 0,
            "highlightthickness": 0,
        }

        if background is not None:

            kwargs["background"] = (
                background
            )

        frame = tk.Frame(
            parent,
            **kwargs,
        )

        frame.pack(
            anchor="w",
            fill="x",
            padx=2,
            pady=2,
        )

        return frame

    def _attach_child(
        self,
        component: GUIComponent,
    ):

        component._window = (
            self._window
        )

        widget = component._realize(
            self._widget
        )

        if isinstance(
            self,
            Row,
        ):

            widget.pack_configure(
                side="left",
                fill="both",
                expand=True,
                padx=4,
                pady=4,
            )

        else:

            widget.pack_configure(
                side=self._pack_side,
                fill="x",
                padx=4,
                pady=4,
            )

    def _realize(
        self,
        parent,
    ):

        widget = super()._realize(
            parent
        )

        for child in self.children:

            self._attach_child(
                child
            )

        return widget


class Panel(Container):

    kind = "Panel"

    _pack_side = "top"


class Column(Container):

    kind = "Column"

    _pack_side = "top"


class Row(Container):

    kind = "Row"

    _pack_side = "left"


# ============================================================
# Window
# ============================================================

class Window:

    def __init__(
        self,
        title: str,
        width: int,
        height: int,
    ):

        if not isinstance(
            title,
            str,
        ):

            raise BlazeTypeError(
                "GUI.Create(title, ...) "
                "expects a string title"
            )

        if (
            not isinstance(
                width,
                (int, float),
            )
            or isinstance(width, bool)
            or width <= 0
        ):

            raise BlazeValueError(
                "GUI.Create(...) width "
                "must be positive"
            )

        if (
            not isinstance(
                height,
                (int, float),
            )
            or isinstance(height, bool)
            or height <= 0
        ):

            raise BlazeValueError(
                "GUI.Create(...) height "
                "must be positive"
            )

        self.title = title

        self.width = int(width)
        self.height = int(height)

        self.children: List[
            GUIComponent
        ] = []

        self._root: Optional[
            tk.Tk
        ] = None

        self._running = False
        self._destroyed = False

        self._style: Dict[
            str,
            Any
        ] = {}

        self._resizable_x = True
        self._resizable_y = True

    # --------------------------------------------------------
    # Safety
    # --------------------------------------------------------

    def _ensure_alive(self):

        if self._destroyed:

            raise _DestroyedError(
                "Window"
            )

    # --------------------------------------------------------
    # Window properties
    # --------------------------------------------------------

    def SetTitle(
        self,
        title: str,
    ):

        self._ensure_alive()

        self.title = title

        if self._root is not None:

            self._root.title(
                title
            )

        return self

    def SetSize(
        self,
        width: int,
        height: int,
    ):

        self._ensure_alive()

        self.width = int(width)
        self.height = int(height)

        if self._root is not None:

            self._root.geometry(
                f"{self.width}x{self.height}"
            )

        return self

    def Resizable(
        self,
        width: bool,
        height: bool,
    ):

        self._ensure_alive()

        self._resizable_x = bool(
            width
        )

        self._resizable_y = bool(
            height
        )

        if self._root is not None:

            self._root.resizable(
                self._resizable_x,
                self._resizable_y,
            )

        return self

    def SetIcon(
        self,
        path: str,
    ):

        self._ensure_alive()

        if not isinstance(
            path,
            str,
        ):

            raise BlazeTypeError(
                "Window.SetIcon(path) "
                "expects a string"
            )

        if self._root is not None:

            try:

                self._root.iconbitmap(
                    path
                )

            except Exception:
                pass

        return self

    # --------------------------------------------------------
    # Window styling
    # --------------------------------------------------------

    def Style(
        self,
        style: Any,
    ):

        self._ensure_alive()

        self._style.update(
            _normalize_style(style)
        )

        if self._root is not None:

            self._apply_style()

        return self

    def SetStyle(
        self,
        style: Any,
    ):

        return self.Style(
            style
        )

    def UseStyle(
        self,
        style: Any,
    ):

        self._ensure_alive()

        if isinstance(
            style,
            GUIStyle,
        ):

            self._style.update(
                style.values
            )

        else:

            self._style.update(
                _normalize_style(style)
            )

        if self._root is not None:

            self._apply_style()

        return self

    def _apply_style(self):

        if self._root is None:
            return

        background = self._style.get(
            "background",
            self._style.get(
                "bg"
            ),
        )

        if background is not None:

            _safe_config(
                self._root,
                "background",
                background,
            )

    # --------------------------------------------------------
    # Add
    # --------------------------------------------------------

    def Add(
        self,
        component: Any,
    ):

        self._ensure_alive()

        if not isinstance(
            component,
            GUIComponent,
        ):

            raise BlazeTypeError(
                "Window.Add(component) "
                "expects a GUI component"
            )

        component._window = self

        self.children.append(
            component
        )

        if self._root is not None:

            self._attach(
                component
            )

        return self

    def _attach(
        self,
        component: GUIComponent,
    ):

        component._window = self

        widget = component._realize(
            self._root
        )

        widget.pack_configure(
            fill="x",
            padx=6,
            pady=4,
        )

    # --------------------------------------------------------
    # Interpreter
    # --------------------------------------------------------

    def _bind_interpreter(
        self,
        components: List[
            GUIComponent
        ],
        interpreter,
    ):

        for component in components:

            if hasattr(
                component,
                "_interpreter",
            ):

                component._interpreter = (
                    interpreter
                )

            if isinstance(
                component,
                Container,
            ):

                self._bind_interpreter(
                    component.children,
                    interpreter,
                )

    # --------------------------------------------------------
    # Run
    # --------------------------------------------------------

    def Run(
        self,
        interpreter=None,
    ):

        self._ensure_alive()

        if self._running:

            raise BlazeRuntimeError(
                "GUI window is already running",
                hint=(
                    "Call app.Run() only once."
                ),
            )

        _set_windows_app_identity()

        self._root = tk.Tk()

        self._root.title(
            self.title
        )

        self._root.geometry(
            f"{self.width}x{self.height}"
        )

        self._root.resizable(
            self._resizable_x,
            self._resizable_y,
        )

        # ----------------------------------------------------
        # Icon
        # ----------------------------------------------------

        icon_path = _get_gui_icon_path()

        if icon_path:

            try:

                self._root.iconbitmap(
                    icon_path
                )

            except Exception:
                pass

        # ----------------------------------------------------
        # Style
        # ----------------------------------------------------

        self._apply_style()

        # ----------------------------------------------------
        # Close
        # ----------------------------------------------------

        self._root.protocol(
            "WM_DELETE_WINDOW",
            self.Close,
        )

        # ----------------------------------------------------
        # Bind callbacks
        # ----------------------------------------------------

        self._bind_interpreter(
            self.children,
            interpreter,
        )

        # ----------------------------------------------------
        # Build UI
        # ----------------------------------------------------

        for component in self.children:

            self._attach(
                component
            )

        self._running = True

        try:

            self._root.mainloop()

        except Exception as error:

            raise BlazeRuntimeError(
                f"GUI event loop error: {error}"
            )

        finally:

            self._running = False

    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    def Close(self):

        if self._destroyed:
            return

        self._running = False
        self._destroyed = True

        if self._root is not None:

            try:

                self._root.destroy()

            finally:

                self._root = None


# ============================================================
# Public Module API
# ============================================================

def create_gui_module(
    interpreter,
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    def Create(
        title: str,
        width: int,
        height: int,
    ) -> Window:

        window = Window(
            title,
            width,
            height,
        )

        original_run = window.Run

        def _run():

            original_run(
                interpreter=interpreter
            )

        window.Run = _run

        return window

    # --------------------------------------------------------
    # Style
    # --------------------------------------------------------

    def Style(
        values: Any = None,
    ) -> GUIStyle:

        return GUIStyle(
            values
        )

    # --------------------------------------------------------
    # Components
    # --------------------------------------------------------

    def _make_label(
        text: str = "",
    ) -> Label:

        return Label(
            text
        )

    def _make_button(
        text: str = "",
    ) -> Button:

        return Button(
            text
        )

    def _make_input(
        placeholder: str = "",
    ) -> Input:

        return Input(
            placeholder
        )

    def _make_password_input(
        placeholder: str = "",
    ) -> PasswordInput:

        return PasswordInput(
            placeholder
        )

    def _make_checkbox(
        text: str = "",
    ) -> Checkbox:

        return Checkbox(
            text
        )

    def _make_text_area(
        placeholder: str = "",
    ) -> TextArea:

        return TextArea(
            placeholder
        )

    def _make_panel() -> Panel:

        return Panel()

    def _make_row() -> Row:

        return Row()

    def _make_column() -> Column:

        return Column()

    # --------------------------------------------------------
    # Exports
    # --------------------------------------------------------

    return {
        "Create": Create,
        "Style": Style,

        "Label": _make_label,
        "Button": _make_button,

        "Input": _make_input,
        "PasswordInput": _make_password_input,

        "Checkbox": _make_checkbox,
        "TextArea": _make_text_area,

        "Panel": _make_panel,
        "Row": _make_row,
        "Column": _make_column,
    }