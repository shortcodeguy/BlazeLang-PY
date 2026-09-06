"""
BlazeLang GUI 2.0 Module
Modern Windows 11 / Fluent Desktop UI Framework for BlazeLang.

Import:
    Import GUI from "gui"
"""

import os
import sys
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Dict, List, Optional, Tuple, Union


from blazelang.errors.error_handler import (
    RuntimeError as BlazeRuntimeError,
    TypeError as BlazeTypeError,
    ValueError as BlazeValueError,
)


# ============================================================
# Windows Native / DWM & DPI System Helpers
# ============================================================

def _set_windows_app_identity():
    """Give Windows a stable AppUserModelID for taskbar grouping."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ShortCodeGuy.BlazeLang.GUI"
        )
    except Exception:
        pass


def _set_windows_dpi_awareness():
    """Enable Windows DPI awareness (Per-Monitor v2 if available)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _set_window_dark_titlebar(hwnd: int, dark: bool):
    """Enable Windows 11 DWM immersive dark mode title bar."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        value = ctypes.c_int(1 if dark else 0)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
        if res != 0:
            DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE_OLD),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
    except Exception:
        pass


def _get_system_theme_mode() -> str:
    """Detect Windows 11 system light vs dark mode from registry."""
    if sys.platform != "win32":
        return "light"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "dark" if val == 0 else "light"
    except Exception:
        return "light"


def _get_system_accent_color() -> str:
    """Detect Windows 11 system accent color from DWM registry."""
    if sys.platform != "win32":
        return "#0078D4"
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\DWM",
        )
        val, _ = winreg.QueryValueEx(key, "AccentColor")
        winreg.CloseKey(key)
        r = val & 0xFF
        g = (val >> 8) & 0xFF
        b = (val >> 16) & 0xFF
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#0078D4"


def _get_base_directory() -> str:
    """Resolve the project or runtime executable directory."""
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
    """Search for the BlazeLang icon."""
    base_dir = _get_base_directory()
    candidates = [
        os.path.join(base_dir, "blaze.ico"),
        os.path.join(base_dir, "assets", "blaze.ico"),
        os.path.join(base_dir, "blazelang", "assets", "blaze.ico"),
        os.path.join(os.path.dirname(__file__), "blaze.ico"),
        os.path.join(os.path.dirname(__file__), "assets", "blaze.ico"),
        os.path.join(os.path.dirname(__file__), "..", "..", "blaze.ico"),
    ]
    seen = set()
    for path in candidates:
        abs_p = os.path.abspath(path)
        if abs_p in seen:
            continue
        seen.add(abs_p)
        if os.path.isfile(abs_p):
            return abs_p
    return None


# ============================================================
# Theme & Modern Windows 11 Fluent Design System
# ============================================================

class ThemeSystem:
    """Windows 11 Fluent Design Theme Palette & Manager."""

    LIGHT = {
        "mode": "light",
        "background": "#f3f3f3",
        "surface": "#ffffff",
        "surfaceSecondary": "#f9f9f9",
        "surfaceTertiary": "#e5e5e5",
        "foreground": "#1a1a1a",
        "foregroundSecondary": "#5d5d5d",
        "border": "#e0e0e0",
        "accent": "#005fb8",
        "accentHover": "#0052a3",
        "accentPressed": "#003d7a",
        "accentText": "#ffffff",
        "danger": "#c42b1c",
        "dangerHover": "#a82317",
        "success": "#0f7b0f",
        "warning": "#9d5d00",
        "cardBg": "#ffffff",
        "cardBorder": "#e5e5e5",
        "inputBg": "#ffffff",
        "inputBorder": "#cecece",
        "inputFocusBorder": "#005fb8",
        "fontFamily": "Segoe UI",
        "fontSize": 10,
        "radius": 6,
    }

    DARK = {
        "mode": "dark",
        "background": "#202020",
        "surface": "#2c2c2c",
        "surfaceSecondary": "#383838",
        "surfaceTertiary": "#444444",
        "foreground": "#ffffff",
        "foregroundSecondary": "#adadad",
        "border": "#3a3a3a",
        "accent": "#60cdff",
        "accentHover": "#52b7e6",
        "accentPressed": "#429bca",
        "accentText": "#000000",
        "danger": "#ff99a4",
        "dangerHover": "#e8808b",
        "success": "#6ccb5f",
        "warning": "#fce100",
        "cardBg": "#2c2c2c",
        "cardBorder": "#3a3a3a",
        "inputBg": "#2b2b2b",
        "inputBorder": "#454545",
        "inputFocusBorder": "#60cdff",
        "fontFamily": "Segoe UI",
        "fontSize": 10,
        "radius": 6,
    }

    def __init__(self):
        self.mode = "system"
        self.custom_overrides = {}

    def get_effective_mode(self) -> str:
        if self.mode == "system":
            return _get_system_theme_mode()
        return self.mode

    def get_palette(self) -> Dict[str, Any]:
        mode = self.get_effective_mode()
        base = dict(self.DARK if mode == "dark" else self.LIGHT)
        if self.mode == "system":
            base["accent"] = _get_system_accent_color()
        base.update(self.custom_overrides)
        return base

    def set_theme(self, theme_config: Any):
        if isinstance(theme_config, str):
            val = theme_config.lower()
            if val in ("system", "light", "dark"):
                self.mode = val
            else:
                raise BlazeValueError(f"Invalid theme mode '{theme_config}'. Use 'system', 'light', or 'dark'.")
        elif isinstance(theme_config, dict) or hasattr(theme_config, "properties"):
            normalized = _normalize_dict(theme_config)
            if "mode" in normalized:
                self.mode = str(normalized["mode"]).lower()
            self.custom_overrides.update(normalized)
        else:
            raise BlazeTypeError("SetTheme expects a string or style dictionary")


_GLOBAL_THEME = ThemeSystem()


# ============================================================
# Helpers
# ============================================================

def _is_blaze_function(value: Any) -> bool:
    return hasattr(value, "__call__") and hasattr(value, "parameters")


def _invoke_callback(interpreter, callback: Any, args: List[Any]):
    if _is_blaze_function(callback):
        return callback(interpreter, args)
    if callable(callback):
        return callback(*args)
    raise BlazeTypeError(f"Expected a callback function, got {type(callback).__name__}")


def _normalize_dict(style: Any) -> Dict[str, Any]:
    if isinstance(style, dict):
        return dict(style)
    if hasattr(style, "properties") and isinstance(style.properties, dict):
        return dict(style.properties)
    if hasattr(style, "__dict__"):
        d = dict(style.__dict__)
        if "values" in d and isinstance(d["values"], dict):
            return dict(d["values"])
        return d
    raise BlazeTypeError("GUI style expects an object or dictionary")


def _safe_config(widget, option: str, value: Any):
    if value is None:
        return
    try:
        widget.configure(**{option: value})
    except (tk.TclError, TypeError, ValueError):
        pass


def _parse_font(style: Dict[str, Any], palette: Dict[str, Any]) -> Tuple[str, int, str, str]:
    font_val = style.get("font")
    family = style.get("font_family", style.get("fontFamily", palette.get("fontFamily", "Segoe UI")))
    size = style.get("font_size", style.get("fontSize", palette.get("fontSize", 10)))
    weight = style.get("font_weight", style.get("fontWeight", "normal"))
    bold = style.get("bold", False) or (weight == "bold" or weight == "semibold")
    italic = style.get("italic", False)

    if isinstance(font_val, (int, float)):
        size = int(font_val)
    elif isinstance(font_val, str):
        return font_val
    elif isinstance(font_val, (tuple, list)):
        return tuple(font_val)

    try:
        size = int(size)
    except Exception:
        size = 10

    w_str = "bold" if bold else "normal"
    s_str = "italic" if italic else "roman"
    return (str(family), size, w_str, s_str)


class _DestroyedError(BlazeRuntimeError):
    def __init__(self, what: str):
        super().__init__(
            f"Cannot operate on '{what}': the GUI window has been closed",
            code="BLZ9001",
            hint="Create a new window with GUI.Create(...) before using components.",
        )


# ============================================================
# GUI Style Object
# ============================================================

class GUIStyle:
    """Reusable GUI style object."""

    def __init__(self, values: Any = None):
        self.values = {} if values is None else _normalize_dict(values)

    def Get(self, key: str, default=None):
        return self.values.get(key, default)

    def Set(self, key: str, value: Any):
        self.values[key] = value
        return self

    def Update(self, values: Any):
        self.values.update(_normalize_dict(values))
        return self


# ============================================================
# Component Base Class
# ============================================================

class GUIComponent:
    """Base class for all BlazeLang GUI components."""
    kind = "Component"

    def __init__(self):
        self._widget: Optional[tk.Widget] = None
        self._window: Optional["Window"] = None
        self._destroyed = False
        self._visible = True
        self._enabled = True
        self._style: Dict[str, Any] = {}
        self._callbacks: Dict[str, Any] = {}
        self._interpreter = None

    def _ensure_alive(self):
        if self._destroyed:
            raise _DestroyedError(self.kind)

    # --------------------------------------------------------
    # Style Methods
    # --------------------------------------------------------

    def Style(self, style: Any):
        self._ensure_alive()
        self._style.update(_normalize_dict(style))
        if self._widget is not None:
            self._apply_style()
        return self

    def SetStyle(self, style: Any):
        return self.Style(style)

    def UseStyle(self, style: Any):
        self._ensure_alive()
        if isinstance(style, GUIStyle):
            self._style.update(style.values)
        else:
            self._style.update(_normalize_dict(style))
        if self._widget is not None:
            self._apply_style()
        return self

    def GetStyle(self, key: str, default=None):
        return self._style.get(key, default)

    def SetStyleValue(self, key: str, value: Any):
        self._ensure_alive()
        self._style[key] = value
        if self._widget is not None:
            self._apply_style()
        return self

    # --------------------------------------------------------
    # Visibility & Enablement
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

    def SetVisible(self, visible: bool):
        return self.Show() if visible else self.Hide()

    def Enable(self):
        self._ensure_alive()
        self._enabled = True
        if self._widget is not None:
            _safe_config(self._widget, "state", "normal")
        return self

    def Disable(self):
        self._ensure_alive()
        self._enabled = False
        if self._widget is not None:
            _safe_config(self._widget, "state", "disabled")
        return self

    def SetEnabled(self, enabled: bool):
        return self.Enable() if enabled else self.Disable()

    def Focus(self):
        self._ensure_alive()
        if self._widget is not None:
            try:
                self._widget.focus_set()
            except Exception:
                pass
        return self

    # --------------------------------------------------------
    # Geometry Helpers
    # --------------------------------------------------------

    def SetWidth(self, width: Any):
        self._style["width"] = width
        if self._widget is not None:
            self._apply_style()
        return self

    def SetHeight(self, height: Any):
        self._style["height"] = height
        if self._widget is not None:
            self._apply_style()
        return self

    def SetPadding(self, padding: Any):
        self._style["padding"] = padding
        if self._widget is not None:
            self._apply_style()
        return self

    # --------------------------------------------------------
    # Event Registration
    # --------------------------------------------------------

    def _register_event(self, event_name: str, callback: Any):
        self._ensure_alive()
        if not (_is_blaze_function(callback) or callable(callback)):
            raise BlazeTypeError(f"{self.kind}.{event_name}(function) expects a callable function")
        self._callbacks[event_name] = callback
        return self

    def OnClick(self, callback: Any):
        return self._register_event("click", callback)

    def OnDoubleClick(self, callback: Any):
        return self._register_event("doubleClick", callback)

    def OnChange(self, callback: Any):
        return self._register_event("change", callback)

    def OnSubmit(self, callback: Any):
        return self._register_event("submit", callback)

    def OnFocus(self, callback: Any):
        return self._register_event("focus", callback)

    def OnBlur(self, callback: Any):
        return self._register_event("blur", callback)

    def OnHover(self, callback: Any):
        return self._register_event("hover", callback)

    def OnKeyDown(self, callback: Any):
        return self._register_event("keyDown", callback)

    def OnKeyUp(self, callback: Any):
        return self._register_event("keyUp", callback)

    def SetContextMenu(self, menu: Any):
        self._ensure_alive()
        if hasattr(menu, "_show_popup"):
            if self._widget is not None:
                self._widget.bind("<Button-3>", lambda e: menu._show_popup(e))
            self._callbacks["contextMenu"] = menu
        return self

    def _dispatch_event(self, event_name: str, *args):
        cb = self._callbacks.get(event_name)
        if cb is not None and self._interpreter is not None:
            try:
                _invoke_callback(self._interpreter, cb, list(args))
            except BlazeRuntimeError:
                raise
            except Exception as err:
                print(f"[BlazeLang GUI] {self.kind} {event_name} error: {err}")

    # --------------------------------------------------------
    # Realization & Styling
    # --------------------------------------------------------

    def _reset_widget_tree(self):
        self._widget = None
        if isinstance(self, Container):
            for child in self.children:
                child._reset_widget_tree()
        elif isinstance(self, NavigationView):
            for _, content_comp, _ in self.nav_items:
                content_comp._reset_widget_tree()
        elif isinstance(self, Tabs):
            for panel in self.tabs_map.values():
                panel._reset_widget_tree()
        elif isinstance(self, SplitView):
            if self.left_comp:
                self.left_comp._reset_widget_tree()
            if self.right_comp:
                self.right_comp._reset_widget_tree()

    def _realize(self, parent: tk.Widget) -> tk.Widget:
        self._ensure_alive()
        if self._widget is not None:
            try:
                if not self._widget.winfo_exists():
                    self._reset_widget_tree()
            except Exception:
                self._reset_widget_tree()

        if self._widget is None:
            self._widget = self._build(parent)
            self._apply_style()
            self._bind_events()
        return self._widget

    def _bind_events(self):
        if self._widget is None:
            return
        if "hover" in self._callbacks:
            self._widget.bind("<Enter>", lambda e: self._dispatch_event("hover", True))
            self._widget.bind("<Leave>", lambda e: self._dispatch_event("hover", False))
        if "focus" in self._callbacks or "blur" in self._callbacks:
            self._widget.bind("<FocusIn>", lambda e: self._dispatch_event("focus"))
            self._widget.bind("<FocusOut>", lambda e: self._dispatch_event("blur"))
        if "keyDown" in self._callbacks:
            self._widget.bind("<KeyPress>", lambda e: self._dispatch_event("keyDown", e.keysym))
        if "keyUp" in self._callbacks:
            self._widget.bind("<KeyRelease>", lambda e: self._dispatch_event("keyUp", e.keysym))
        if "doubleClick" in self._callbacks:
            self._widget.bind("<Double-Button-1>", lambda e: self._dispatch_event("doubleClick"))
        if "contextMenu" in self._callbacks:
            menu = self._callbacks["contextMenu"]
            self._widget.bind("<Button-3>", lambda e: menu._show_popup(e))

    def _apply_style(self):
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        style = self._style

        bg = style.get("background", style.get("bg", palette["surface"]))
        fg = style.get("foreground", style.get("color", palette["foreground"]))
        font = _parse_font(style, palette)
        width = style.get("width")
        height = style.get("height")
        cursor = style.get("cursor")
        relief = style.get("relief", "flat")
        border = style.get("border", style.get("borderWidth", 0))

        _safe_config(self._widget, "background", bg)
        _safe_config(self._widget, "bg", bg)
        _safe_config(self._widget, "foreground", fg)
        _safe_config(self._widget, "fg", fg)
        _safe_config(self._widget, "font", font)
        _safe_config(self._widget, "relief", relief)
        _safe_config(self._widget, "bd", border)
        _safe_config(self._widget, "borderwidth", border)
        if cursor is not None:
            _safe_config(self._widget, "cursor", cursor)

        if width is not None and isinstance(width, (int, float)):
            _safe_config(self._widget, "width", int(width))
        if height is not None and isinstance(height, (int, float)):
            _safe_config(self._widget, "height", int(height))


# ============================================================
# Text & Label Components
# ============================================================

class Label(GUIComponent):
    kind = "Label"

    def __init__(self, text_or_opts: Any = "", opts: Any = None):
        super().__init__()
        options = None
        if isinstance(text_or_opts, dict) or hasattr(text_or_opts, "properties"):
            options = _normalize_dict(text_or_opts)
            self.text = str(options.get("text", options.get("value", "")))
        else:
            self.text = str(text_or_opts)
            if opts:
                options = _normalize_dict(opts)

        if options:
            if "size" in options:
                self._style["fontSize"] = options["size"]
            if "weight" in options:
                self._style["fontWeight"] = options["weight"]
            if "alignment" in options:
                self._style["alignment"] = options["alignment"]

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        align_map = {"center": "center", "right": "e", "left": "w"}
        anchor = align_map.get(self._style.get("alignment", "left"), "w")
        widget = tk.Label(
            parent,
            text=self.text,
            anchor=anchor,
            bg=palette["surface"],
            fg=palette["foreground"],
            bd=0,
        )
        return widget

    def SetText(self, text: str):
        self._ensure_alive()
        self.text = str(text)
        if self._widget is not None:
            self._widget.config(text=self.text)
        return self

    def GetText(self) -> str:
        return self.text

    def SetFontSize(self, size: int):
        return self.SetStyleValue("fontSize", size)

    def SetFontWeight(self, weight: str):
        return self.SetStyleValue("fontWeight", weight)

    def SetAlignment(self, alignment: str):
        return self.SetStyleValue("alignment", alignment)


class Text(Label):
    kind = "Text"


# ============================================================
# Icon Component & Renderer
# ============================================================

class Icon(GUIComponent):
    kind = "Icon"

    ICON_MAP = {
        "settings": "⚙",
        "search": "🔍",
        "save": "💾",
        "folder": "📁",
        "trash": "🗑",
        "home": "🏠",
        "edit": "✏",
        "plus": "➕",
        "minus": "➖",
        "check": "✔",
        "close": "✖",
        "user": "👤",
        "refresh": "🔄",
        "info": "ℹ",
        "warning": "⚠",
    }

    def __init__(self, name: str = "home", size: int = 16):
        super().__init__()
        self.name = name
        self.size = size

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        glyph = self.ICON_MAP.get(self.name.lower(), self.name)
        widget = tk.Label(
            parent,
            text=glyph,
            font=("Segoe UI Symbol", self.size),
            bg=palette["surface"],
            fg=palette["foreground"],
            bd=0,
        )
        return widget


# ============================================================
# Button Component
# ============================================================

class Button(GUIComponent):
    kind = "Button"

    def __init__(self, text_or_opts: Any = ""):
        super().__init__()
        self.text = ""
        self.icon = None
        self.variant = "secondary"

        if isinstance(text_or_opts, dict) or hasattr(text_or_opts, "properties"):
            opts = _normalize_dict(text_or_opts)
            self.text = str(opts.get("text", opts.get("value", "")))
            self.icon = opts.get("icon")
            self.variant = opts.get("variant", "secondary")
            if "radius" in opts:
                self._style["radius"] = opts["radius"]
            if "height" in opts:
                self._style["height"] = opts["height"]
        else:
            self.text = str(text_or_opts)

    def _build(self, parent: tk.Widget) -> tk.Widget:
        display_text = self.text
        if self.icon:
            glyph = Icon.ICON_MAP.get(str(self.icon).lower(), str(self.icon))
            display_text = f"{glyph}  {self.text}"

        widget = tk.Button(
            parent,
            text=display_text,
            command=self._on_click_cmd,
            relief="flat",
            bd=0,
            cursor="hand2",
            takefocus=True,
        )
        return widget

    def SetText(self, text: str):
        self._ensure_alive()
        self.text = str(text)
        if self._widget is not None:
            display_text = self.text
            if self.icon:
                glyph = Icon.ICON_MAP.get(str(self.icon).lower(), str(self.icon))
                display_text = f"{glyph}  {self.text}"
            self._widget.config(text=display_text)
        return self

    def SetIcon(self, icon: str):
        self._ensure_alive()
        self.icon = icon
        return self.SetText(self.text)

    def SetVariant(self, variant: str):
        self.variant = variant
        if self._widget is not None:
            self._apply_style()
        return self

    def _on_click_cmd(self):
        self._dispatch_event("click")

    def _apply_style(self):
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        variant = self._style.get("variant", self.variant)

        bg = palette["surfaceSecondary"]
        fg = palette["foreground"]
        active_bg = palette["surfaceTertiary"]

        if variant == "primary":
            bg = palette["accent"]
            fg = palette["accentText"]
            active_bg = palette["accentHover"]
        elif variant == "danger":
            bg = palette["danger"]
            fg = "#ffffff"
            active_bg = palette["dangerHover"]
        elif variant == "success":
            bg = palette["success"]
            fg = "#ffffff"
            active_bg = palette["success"]
        elif variant == "outline":
            bg = palette["surface"]
            fg = palette["foreground"]
            active_bg = palette["surfaceSecondary"]
            _safe_config(self._widget, "highlightbackground", palette["border"])
            _safe_config(self._widget, "highlightthickness", 1)
        elif variant == "subtle":
            bg = palette["surface"]
            fg = palette["foreground"]
            active_bg = palette["surfaceSecondary"]

        bg = self._style.get("background", self._style.get("bg", bg))
        fg = self._style.get("foreground", self._style.get("color", fg))
        active_bg = self._style.get("active_background", self._style.get("hover_background", active_bg))

        _safe_config(self._widget, "background", bg)
        _safe_config(self._widget, "bg", bg)
        _safe_config(self._widget, "foreground", fg)
        _safe_config(self._widget, "fg", fg)
        _safe_config(self._widget, "activebackground", active_bg)
        _safe_config(self._widget, "activeforeground", fg)
        _safe_config(self._widget, "font", _parse_font(self._style, palette))

        # Smooth interactive hover feedback
        try:
            self._widget.bind("<Enter>", lambda e, b=bg, ab=active_bg: _safe_config(self._widget, "bg", ab), add="+")
            self._widget.bind("<Leave>", lambda e, b=bg: _safe_config(self._widget, "bg", b), add="+")
        except Exception:
            pass

        height = self._style.get("height")
        if height is not None and isinstance(height, (int, float)):
            _safe_config(self._widget, "height", int(height))


# ============================================================
# Input Components (Input, PasswordInput)
# ============================================================

class Input(GUIComponent):
    kind = "Input"
    _show_char = None

    def __init__(self, val_or_opts: Any = ""):
        super().__init__()
        self.placeholder = ""
        self.initial_value = ""
        self.readonly = False

        if isinstance(val_or_opts, dict) or hasattr(val_or_opts, "properties"):
            opts = _normalize_dict(val_or_opts)
            self.initial_value = str(opts.get("value", ""))
            self.placeholder = str(opts.get("placeholder", ""))
            self.readonly = bool(opts.get("readonly", opts.get("readOnly", False)))
            if "alignment" in opts:
                self._style["alignment"] = opts["alignment"]
            if "fontSize" in opts:
                self._style["fontSize"] = opts["fontSize"]
        else:
            self.initial_value = str(val_or_opts)

        self._var: Optional[tk.StringVar] = None
        self._changing = False

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        self._var = tk.StringVar(value=self.initial_value)

        justify = self._style.get("alignment", "left")

        frame = tk.Frame(parent, bg=palette["inputBg"], bd=1, relief="solid")
        frame.configure(highlightbackground=palette["inputBorder"], highlightcolor=palette["inputFocusBorder"], highlightthickness=1)

        kwargs = {}
        if self._show_char is not None:
            kwargs["show"] = self._show_char

        entry = tk.Entry(
            frame,
            textvariable=self._var,
            relief="flat",
            bd=0,
            bg=palette["inputBg"],
            fg=palette["foreground"],
            justify=justify,
            state="readonly" if self.readonly else "normal",
            insertbackground=palette["foreground"],
            **kwargs,
        )
        entry.pack(fill="both", expand=True, padx=6, pady=6)

        if hasattr(self, "_add_extra_widgets"):
            self._add_extra_widgets(frame, entry)

        self._var.trace_add("write", lambda *_: self._on_change_cmd())
        entry.bind("<Return>", lambda e: self._dispatch_event("submit", self.GetValue()))

        return frame

    def _on_change_cmd(self):
        if not self._changing:
            self._dispatch_event("change", self.GetValue())

    def GetValue(self) -> str:
        self._ensure_alive()
        return self._var.get() if self._var is not None else self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._var is not None:
            self._changing = True
            try:
                self._var.set(self.initial_value)
            finally:
                self._changing = False
        return self

    def SetPlaceholder(self, placeholder: str):
        self.placeholder = str(placeholder)
        return self

    def SetReadOnly(self, readonly: bool):
        self.readonly = bool(readonly)
        if self._widget is not None:
            _safe_config(self._widget, "state", "readonly" if self.readonly else "normal")
        return self

    def Clear(self):
        return self.SetValue("")


class PasswordInput(Input):
    kind = "PasswordInput"
    _show_char = "•"

    def __init__(self, val_or_opts: Any = ""):
        super().__init__(val_or_opts)
        self.reveal_enabled = True

    def _add_extra_widgets(self, frame: tk.Frame, entry: tk.Entry):
        palette = _GLOBAL_THEME.get_palette()
        btn = tk.Button(
            frame,
            text="👁",
            bd=0,
            relief="flat",
            bg=palette["inputBg"],
            fg=palette["foregroundSecondary"],
            cursor="hand2",
        )
        btn.pack(side="right", padx=4)
        showing = [True]

        def toggle_reveal():
            showing[0] = not showing[0]
            entry.config(show="•" if showing[0] else "")

        btn.config(command=toggle_reveal)


# ============================================================
# Checkbox, Toggle Switch & Radio Components
# ============================================================

class Checkbox(GUIComponent):
    kind = "Checkbox"

    def __init__(self, text_or_opts: Any = ""):
        super().__init__()
        self.text = ""
        self.initial_checked = False

        if isinstance(text_or_opts, dict) or hasattr(text_or_opts, "properties"):
            opts = _normalize_dict(text_or_opts)
            self.text = str(opts.get("text", ""))
            self.initial_checked = bool(opts.get("checked", False))
        else:
            self.text = str(text_or_opts)

        self._var: Optional[tk.BooleanVar] = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        self._var = tk.BooleanVar(value=self.initial_checked)

        widget = tk.Checkbutton(
            parent,
            text=self.text,
            variable=self._var,
            command=lambda: self._dispatch_event("change", self.IsChecked()),
            anchor="w",
            bd=0,
            bg=palette["surface"],
            fg=palette["foreground"],
            activebackground=palette["surface"],
            activeforeground=palette["foreground"],
            selectcolor=palette["surfaceSecondary"],
            highlightthickness=0,
        )
        return widget

    def IsChecked(self) -> bool:
        self._ensure_alive()
        return bool(self._var.get()) if self._var is not None else self.initial_checked

    def SetChecked(self, value: bool):
        self._ensure_alive()
        self.initial_checked = bool(value)
        if self._var is not None:
            self._var.set(self.initial_checked)
        return self

    def SetText(self, text: str):
        self.text = str(text)
        if self._widget is not None:
            self._widget.config(text=self.text)
        return self


CheckBox = Checkbox


class Toggle(GUIComponent):
    """Windows 11 Modern Pill Toggle Switch Widget."""
    kind = "Toggle"

    def __init__(self, text_or_opts: Any = ""):
        super().__init__()
        self.text = ""
        self.initial_checked = False

        if isinstance(text_or_opts, dict) or hasattr(text_or_opts, "properties"):
            opts = _normalize_dict(text_or_opts)
            self.text = str(opts.get("text", ""))
            self.initial_checked = bool(opts.get("checked", False))
        else:
            self.text = str(text_or_opts)

        self.checked = self.initial_checked

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        frame = tk.Frame(parent, bg=palette["surface"])

        self.canvas = tk.Canvas(frame, width=40, height=20, bg=palette["surface"], highlightthickness=0, cursor="hand2")
        self.canvas.pack(side="left")

        self.lbl = tk.Label(frame, text=self.text, bg=palette["surface"], fg=palette["foreground"])
        self.lbl.pack(side="left", padx=8)

        self._draw_switch()

        self.canvas.bind("<Button-1>", lambda e: self.toggle())
        self.lbl.bind("<Button-1>", lambda e: self.toggle())

        return frame

    def _draw_switch(self):
        palette = _GLOBAL_THEME.get_palette()
        self.canvas.delete("all")
        bg_col = palette["accent"] if self.checked else palette["surfaceTertiary"]
        knob_col = palette["accentText"] if self.checked else palette["foregroundSecondary"]

        # Pill background
        self.canvas.create_oval(2, 2, 20, 18, fill=bg_col, outline="")
        self.canvas.create_oval(20, 2, 38, 18, fill=bg_col, outline="")
        self.canvas.create_rectangle(11, 2, 29, 18, fill=bg_col, outline="")

        # Knob
        kx = 22 if self.checked else 4
        self.canvas.create_oval(kx, 4, kx + 14, 16, fill=knob_col, outline="")

    def toggle(self):
        self.checked = not self.checked
        self._draw_switch()
        self._dispatch_event("change", self.checked)

    def IsChecked(self) -> bool:
        return self.checked

    def SetChecked(self, value: bool):
        self.checked = bool(value)
        if hasattr(self, "canvas"):
            self._draw_switch()
        return self


Switch = Toggle


class Radio(GUIComponent):
    kind = "Radio"
    _GROUPS: Dict[str, Any] = {}
    _INITIAL_GROUPS: Dict[str, str] = {}

    def __init__(self, text: str = "", group: str = "default", value: str = None):
        super().__init__()
        self.text = text
        self.group = group
        self.value = value if value is not None else text

    @classmethod
    def _get_group_var(cls, group: str) -> Optional[tk.StringVar]:
        if group not in cls._GROUPS:
            if tk._default_root is not None:
                initial = cls._INITIAL_GROUPS.get(group, "")
                cls._GROUPS[group] = tk.StringVar(value=initial)
            else:
                return None
        return cls._GROUPS[group]

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        var = self._get_group_var(self.group)
        if var is None:
            initial = Radio._INITIAL_GROUPS.get(self.group, "")
            Radio._GROUPS[self.group] = tk.StringVar(master=parent, value=initial)
            var = Radio._GROUPS[self.group]

        widget = tk.Radiobutton(
            parent,
            text=self.text,
            value=self.value,
            variable=var,
            command=lambda: self._dispatch_event("change", self.GetValue()),
            anchor="w",
            bd=0,
            bg=palette["surface"],
            fg=palette["foreground"],
            activebackground=palette["surface"],
            activeforeground=palette["foreground"],
            selectcolor=palette["surfaceSecondary"],
            highlightthickness=0,
        )
        return widget

    def IsChecked(self) -> bool:
        var = self._get_group_var(self.group)
        if var is not None:
            return var.get() == self.value
        return Radio._INITIAL_GROUPS.get(self.group) == self.value

    def SetChecked(self, checked: bool):
        if checked:
            Radio._INITIAL_GROUPS[self.group] = self.value
            var = self._get_group_var(self.group)
            if var is not None:
                var.set(self.value)
        return self

    def GetValue(self) -> str:
        var = self._get_group_var(self.group)
        if var is not None:
            return var.get()
        return Radio._INITIAL_GROUPS.get(self.group, "")


# ============================================================
# ComboBox, Slider, ProgressBar & TextArea
# ============================================================

class ComboBox(GUIComponent):
    kind = "ComboBox"

    def __init__(self, items_or_opts: Any = None):
        super().__init__()
        self.items = []
        self.initial_value = ""

        if isinstance(items_or_opts, (list, tuple)):
            self.items = [str(x) for x in items_or_opts]
        elif isinstance(items_or_opts, dict) or hasattr(items_or_opts, "properties"):
            opts = _normalize_dict(items_or_opts)
            self.items = [str(x) for x in opts.get("items", [])]
            self.initial_value = str(opts.get("value", ""))

        if self.items and not self.initial_value:
            self.initial_value = self.items[0]

        self._combo: Optional[ttk.Combobox] = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        self._combo = ttk.Combobox(parent, values=self.items, state="readonly")
        if self.initial_value:
            self._combo.set(self.initial_value)
        self._combo.bind("<<ComboboxSelected>>", lambda e: self._dispatch_event("change", self.GetValue()))
        return self._combo

    def GetValue(self) -> str:
        self._ensure_alive()
        return self._combo.get() if self._combo is not None else self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._combo is not None:
            self._combo.set(self.initial_value)
        return self

    def AddItem(self, item: str):
        self.items.append(str(item))
        if self._combo is not None:
            self._combo["values"] = self.items
        return self

    def RemoveItem(self, item: str):
        if str(item) in self.items:
            self.items.remove(str(item))
            if self._combo is not None:
                self._combo["values"] = self.items
        return self

    def Clear(self):
        self.items.clear()
        if self._combo is not None:
            self._combo["values"] = []
            self._combo.set("")
        return self


class Slider(GUIComponent):
    kind = "Slider"

    def __init__(self, min_or_opts: Any = 0, max_val: float = 100, val: float = 50):
        super().__init__()
        self.min = 0
        self.max = 100
        self.value = 50

        if isinstance(min_or_opts, dict) or hasattr(min_or_opts, "properties"):
            opts = _normalize_dict(min_or_opts)
            self.min = float(opts.get("min", 0))
            self.max = float(opts.get("max", 100))
            self.value = float(opts.get("value", 50))
        else:
            self.min = float(min_or_opts)
            self.max = float(max_val)
            self.value = float(val)

        self._scale: Optional[tk.Scale] = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        self._scale = tk.Scale(
            parent,
            from_=self.min,
            to=self.max,
            orient="horizontal",
            command=lambda v: self._dispatch_event("change", float(v)),
            bg=palette["surface"],
            fg=palette["foreground"],
            highlightthickness=0,
            bd=0,
            troughcolor=palette["surfaceSecondary"],
            activebackground=palette["accent"],
        )
        self._scale.set(self.value)
        return self._scale

    def GetValue(self) -> float:
        self._ensure_alive()
        return float(self._scale.get()) if self._scale is not None else self.value

    def SetValue(self, value: float):
        self._ensure_alive()
        self.value = float(value)
        if self._scale is not None:
            self._scale.set(self.value)
        return self


class ProgressBar(GUIComponent):
    kind = "ProgressBar"

    def __init__(self, val_or_opts: Any = 0):
        super().__init__()
        self.value = 0
        if isinstance(val_or_opts, dict) or hasattr(val_or_opts, "properties"):
            opts = _normalize_dict(val_or_opts)
            self.value = float(opts.get("value", 0))
        else:
            self.value = float(val_or_opts)
        self._bar: Optional[ttk.Progressbar] = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        self._bar = ttk.Progressbar(parent, value=self.value, maximum=100)
        return self._bar

    def SetValue(self, value: float):
        self._ensure_alive()
        self.value = float(value)
        if self._bar is not None:
            self._bar["value"] = self.value
        return self

    def SetIndeterminate(self, indeterminate: bool):
        if self._bar is not None:
            self._bar["mode"] = "indeterminate" if indeterminate else "determinate"
            if indeterminate:
                self._bar.start(10)
            else:
                self._bar.stop()
        return self


class TextArea(GUIComponent):
    kind = "TextArea"

    def __init__(self, placeholder_or_opts: Any = ""):
        super().__init__()
        self.placeholder = ""
        self.wrap = "word"
        self.initial_value = ""

        if isinstance(placeholder_or_opts, dict) or hasattr(placeholder_or_opts, "properties"):
            opts = _normalize_dict(placeholder_or_opts)
            self.placeholder = str(opts.get("placeholder", ""))
            self.initial_value = str(opts.get("value", ""))
            self.wrap = "word" if opts.get("wrap", True) else "none"
        else:
            self.placeholder = str(placeholder_or_opts)

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        widget = tk.Text(
            parent,
            height=6,
            width=40,
            relief="flat",
            bd=0,
            wrap=self.wrap,
            bg=palette["inputBg"],
            fg=palette["foreground"],
            insertbackground=palette["foreground"],
            highlightbackground=palette["inputBorder"],
            highlightcolor=palette["inputFocusBorder"],
            highlightthickness=1,
        )
        if self.initial_value:
            widget.insert("1.0", self.initial_value)
        widget.bind("<<Modified>>", lambda e: self._on_mod(widget))
        return widget

    def _on_mod(self, widget: tk.Text):
        if widget.edit_modified():
            widget.edit_modified(False)
            self._dispatch_event("change", self.GetValue())

    def GetValue(self) -> str:
        self._ensure_alive()
        return self._widget.get("1.0", "end-1c") if self._widget is not None else self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._widget is not None:
            self._widget.delete("1.0", "end")
            self._widget.insert("1.0", self.initial_value)
        return self

    def Append(self, text: str):
        self._ensure_alive()
        self.initial_value += str(text)
        if self._widget is not None:
            self._widget.insert("end", str(text))
        return self

    def Clear(self):
        return self.SetValue("")


# ============================================================
# Image Component
# ============================================================

class Image(GUIComponent):
    kind = "Image"

    def __init__(self, src_or_opts: Any = ""):
        super().__init__()
        self.source = ""
        self.req_width = None
        self.req_height = None
        self.stretch = "contain"

        if isinstance(src_or_opts, dict) or hasattr(src_or_opts, "properties"):
            opts = _normalize_dict(src_or_opts)
            self.source = opts.get("source", opts.get("src", ""))
            self.req_width = opts.get("width")
            self.req_height = opts.get("height")
            self.stretch = opts.get("stretch", "contain")
        else:
            self.source = src_or_opts

        self._img_ref = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        lbl = tk.Label(parent, bg=palette["surface"], bd=0)
        self._update_image(lbl)
        return lbl

    def _update_image(self, lbl: tk.Label):
        if not self.source:
            return
        try:
            from PIL import Image as PILImage, ImageTk
            pil_img = None

            if hasattr(self.source, "_image"):  # BlazeImage
                pil_img = self.source._image
            elif hasattr(self.source, "AddListener") and callable(getattr(self.source, "AddListener", None)):  # BlazeVideo
                def on_frame(frame):
                    if not lbl.winfo_exists():
                        return
                    try:
                        if self.req_width and self.req_height:
                            frame = frame.resize((int(self.req_width), int(self.req_height)))
                        self._img_ref = ImageTk.PhotoImage(frame)
                        lbl.config(image=self._img_ref)
                    except Exception:
                        pass

                self.source.AddListener(on_frame)
                if hasattr(self.source, "_bind_widget"):
                    self.source._bind_widget(lbl)
                pil_img = self.source.GetFrame()
            elif isinstance(self.source, str) and os.path.isfile(self.source):
                pil_img = PILImage.open(self.source)

            if pil_img is not None:
                if self.req_width and self.req_height:
                    pil_img = pil_img.resize((int(self.req_width), int(self.req_height)))
                self._img_ref = ImageTk.PhotoImage(pil_img)
                lbl.config(image=self._img_ref)
                return
        except Exception:
            pass

        if isinstance(self.source, str) and os.path.isfile(self.source):
            try:
                self._img_ref = tk.PhotoImage(file=self.source)
                lbl.config(image=self._img_ref)
            except Exception:
                pass

    def SetSource(self, source: Any):
        self.source = source
        if self._widget is not None:
            self._update_image(self._widget)
        return self

    def SetSize(self, width: int, height: int):
        self.req_width = width
        self.req_height = height
        if self._widget is not None:
            self._update_image(self._widget)
        return self

    def SetStretch(self, stretch: str):
        self.stretch = stretch
        return self


class VideoWidget(GUIComponent):
    """Component for displaying and rendering live video streams."""
    kind = "Video"

    def __init__(self, video_or_opts: Any = ""):
        super().__init__()
        self.video = None
        self.req_width = None
        self.req_height = None

        if isinstance(video_or_opts, dict) or hasattr(video_or_opts, "properties"):
            opts = _normalize_dict(video_or_opts)
            self.video = opts.get("source", opts.get("video", None))
            self.req_width = opts.get("width")
            self.req_height = opts.get("height")
        else:
            self.video = video_or_opts

        self._img_ref = None

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        lbl = tk.Label(parent, bg=palette["surface"], bd=0)
        self._attach_video(lbl)
        return lbl

    def _attach_video(self, lbl: tk.Label):
        if self.video is None:
            return
        from PIL import ImageTk

        def on_frame(pil_img):
            if not lbl.winfo_exists():
                return
            try:
                if self.req_width and self.req_height:
                    pil_img = pil_img.resize((int(self.req_width), int(self.req_height)))
                self._img_ref = ImageTk.PhotoImage(pil_img)
                lbl.config(image=self._img_ref)
            except Exception:
                pass

        if hasattr(self.video, "AddListener"):
            self.video.AddListener(on_frame)
            if hasattr(self.video, "_bind_widget"):
                self.video._bind_widget(lbl)

    def SetVideo(self, video: Any):
        self.video = video
        if self._widget is not None:
            self._attach_video(self._widget)
        return self

    def SetSource(self, source: Any):
        return self.SetVideo(source)

    def SetSize(self, width: int, height: int):
        self.req_width = width
        self.req_height = height
        if self._widget is not None:
            self._attach_video(self._widget)
        return self


# ============================================================
# Containers & Layout Components
# ============================================================

class Container(GUIComponent):
    kind = "Container"
    _pack_side = "top"

    def __init__(self, opts: Any = None):
        super().__init__()
        self.children: List[GUIComponent] = []
        if opts:
            self._style.update(_normalize_dict(opts))

    def Add(self, *components: Any):
        self._ensure_alive()
        for comp in components:
            if isinstance(comp, (list, tuple)):
                self.Add(*comp)
                continue
            if not isinstance(comp, GUIComponent):
                raise BlazeTypeError(f"{self.kind}.Add expects GUI components, got {type(comp).__name__}")
            self.children.append(comp)
            comp._window = self._window
            if self._widget is not None:
                self._attach_child(comp)
        return self

    def Remove(self, component: GUIComponent):
        self._ensure_alive()
        if component in self.children:
            self.children.remove(component)
            if component._widget is not None:
                component._widget.destroy()
                component._widget = None
        return self

    def Clear(self):
        self._ensure_alive()
        for child in list(self.children):
            self.Remove(child)
        return self

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", self._style.get("bg", palette["surface"]))
        frame = tk.Frame(parent, bg=bg, bd=0, highlightthickness=0)
        return frame

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        widget = component._realize(self._widget)
        if isinstance(self, Row):
            widget.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        else:
            widget.pack(side=self._pack_side, fill="x", padx=2, pady=2)

    def _realize(self, parent: tk.Widget) -> tk.Widget:
        widget = super()._realize(parent)
        for child in self.children:
            self._attach_child(child)
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


class Stack(Container):
    kind = "Stack"

    def __init__(self, opts: Any = None):
        super().__init__(opts)
        opts_dict = _normalize_dict(opts) if opts else {}
        direction = opts_dict.get("direction", "vertical")
        self._pack_side = "left" if direction == "horizontal" else "top"


class Card(Container):
    kind = "Card"

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", palette["cardBg"])
        border = self._style.get("border", palette["cardBorder"])
        frame = tk.Frame(parent, bg=bg, bd=1, relief="solid")
        frame.configure(highlightbackground=border, highlightthickness=1)
        return frame

    def SetRadius(self, radius: int):
        self._style["radius"] = radius
        return self


class Grid(Container):
    kind = "Grid"

    def __init__(self, opts: Any = None):
        super().__init__(opts)
        opts_dict = _normalize_dict(opts) if opts else {}
        self.cols = int(opts_dict.get("columns", 2))
        self.rows = int(opts_dict.get("rows", 2))
        self.spacing = int(opts_dict.get("spacing", 4))
        self.grid_positions: Dict[GUIComponent, Tuple[int, int, int, int]] = {}
        self._auto_idx = 0

    def Add(self, component: Any, row: Optional[int] = None, col: Optional[int] = None, rowspan: int = 1, colspan: int = 1):
        self._ensure_alive()
        if not isinstance(component, GUIComponent):
            raise BlazeTypeError(f"Grid.Add expects a GUIComponent, got {type(component).__name__}")

        if row is None or col is None:
            r = self._auto_idx // self.cols
            c = self._auto_idx % self.cols
            self._auto_idx += 1
        else:
            r, c = int(row), int(col)

        self.children.append(component)
        self.grid_positions[component] = (r, c, int(rowspan), int(colspan))
        component._window = self._window

        if self._widget is not None:
            self._attach_child(component)
        return self

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        frame = tk.Frame(parent, bg=palette["surface"], bd=0)
        for c in range(self.cols):
            frame.columnconfigure(c, weight=1)
        for r in range(self.rows):
            frame.rowconfigure(r, weight=1)
        return frame

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        widget = component._realize(self._widget)
        r, c, rs, cs = self.grid_positions.get(component, (0, 0, 1, 1))
        widget.grid(row=r, column=c, rowspan=rs, columnspan=cs, sticky="nsew", padx=self.spacing, pady=self.spacing)


class ScrollView(Container):
    kind = "ScrollView"

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        outer = tk.Frame(parent, bg=palette["surface"])

        canvas = tk.Canvas(outer, bg=palette["surface"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=palette["surface"])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._inner_frame = scrollable_frame
        return outer

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        inner = getattr(self, "_inner_frame", self._widget)
        widget = component._realize(inner)
        widget.pack(side="top", fill="x", padx=4, pady=4)


class SplitView(GUIComponent):
    kind = "SplitView"

    def __init__(self, opts: Any = None):
        super().__init__()
        opts_dict = _normalize_dict(opts) if opts else {}
        self.orientation = opts_dict.get("orientation", "horizontal")
        self.ratio = float(opts_dict.get("ratio", 0.3))
        self.left_comp = None
        self.right_comp = None

    def SetLeft(self, component: GUIComponent):
        self.left_comp = component
        return self

    def SetRight(self, component: GUIComponent):
        self.right_comp = component
        return self

    SetTop = SetLeft
    SetBottom = SetRight

    def _build(self, parent: tk.Widget) -> tk.Widget:
        orient = "horizontal" if self.orientation == "horizontal" else "vertical"
        paned = ttk.PanedWindow(parent, orient=orient)
        if self.left_comp:
            w1 = self.left_comp._realize(paned)
            paned.add(w1, weight=1)
        if self.right_comp:
            w2 = self.right_comp._realize(paned)
            paned.add(w2, weight=3)
        return paned


class Spacer(GUIComponent):
    kind = "Spacer"

    def __init__(self, size_or_opts: Any = 12):
        super().__init__()
        self.size = 12
        self.expand = False
        if isinstance(size_or_opts, dict) or hasattr(size_or_opts, "properties"):
            opts = _normalize_dict(size_or_opts)
            self.expand = bool(opts.get("expand", False))
            self.size = int(opts.get("size", 12))
        elif isinstance(size_or_opts, (int, float)):
            self.size = int(size_or_opts)

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        frame = tk.Frame(parent, bg=palette["surface"], height=self.size, width=self.size)
        return frame


class Divider(GUIComponent):
    kind = "Divider"

    def __init__(self, orient: str = "horizontal"):
        super().__init__()
        self.orient = orient

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        if self.orient == "horizontal":
            sep = tk.Frame(parent, bg=palette["border"], height=1)
        else:
            sep = tk.Frame(parent, bg=palette["border"], width=1)
        return sep


# ============================================================
# Advanced Navigation & Data Views (Tabs, Navigation, Table, List)
# ============================================================

class Tabs(GUIComponent):
    kind = "Tabs"

    def __init__(self):
        super().__init__()
        self.tabs_map: Dict[str, Container] = {}
        self._notebook: Optional[ttk.Notebook] = None

    def Add(self, title: str) -> Container:
        panel = Container()
        self.tabs_map[title] = panel
        if self._notebook is not None:
            w = panel._realize(self._notebook)
            self._notebook.add(w, text=title)
        return panel

    def _build(self, parent: tk.Widget) -> tk.Widget:
        self._notebook = ttk.Notebook(parent)
        for title, panel in self.tabs_map.items():
            w = panel._realize(self._notebook)
            self._notebook.add(w, text=title)
        self._notebook.bind("<<NotebookTabChanged>>", lambda e: self._dispatch_event("change", self.GetSelected()))
        return self._notebook

    def Select(self, title: str):
        if title in self.tabs_map and self._notebook is not None:
            idx = list(self.tabs_map.keys()).index(title)
            self._notebook.select(idx)
        return self

    def GetSelected(self) -> str:
        if self._notebook is not None:
            try:
                idx = self._notebook.index(self._notebook.select())
                return list(self.tabs_map.keys())[idx]
            except Exception:
                pass
        return ""

    def Remove(self, title: str):
        if title in self.tabs_map:
            idx = list(self.tabs_map.keys()).index(title)
            del self.tabs_map[title]
            if self._notebook is not None:
                self._notebook.forget(idx)
        return self


class NavigationView(GUIComponent):
    """Windows 11 Modern Sidebar Navigation View."""
    kind = "NavigationView"

    def __init__(self):
        super().__init__()
        self.nav_items: List[Tuple[str, GUIComponent, str]] = []
        self.active_title = ""

    def Add(self, title: str, content: GUIComponent, icon: str = "home"):
        self.nav_items.append((title, content, icon))
        if not self.active_title:
            self.active_title = title
        return self

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        root_frame = tk.Frame(parent, bg=palette["surface"])

        # Sidebar
        sidebar = tk.Frame(root_frame, bg=palette["surfaceSecondary"], width=180)
        sidebar.pack(side="left", fill="y")

        # Content Container
        self.content_area = tk.Frame(root_frame, bg=palette["surface"])
        self.content_area.pack(side="right", fill="both", expand=True)

        self.btn_map = {}
        for title, content, icon_name in self.nav_items:
            glyph = Icon.ICON_MAP.get(icon_name.lower(), "📄")
            btn = tk.Button(
                sidebar,
                text=f"  {glyph}  {title}",
                anchor="w",
                relief="flat",
                bd=0,
                bg=palette["surfaceSecondary"],
                fg=palette["foreground"],
                activebackground=palette["surfaceTertiary"],
                font=("Segoe UI", 10),
                cursor="hand2",
                command=lambda t=title: self.Select(t),
            )
            btn.pack(fill="x", padx=4, pady=2)
            self.btn_map[title] = btn

        self._show_active_content()
        return root_frame

    def Select(self, title: str):
        self.active_title = title
        self._show_active_content()
        self._dispatch_event("change", title)
        return self

    def GetSelected(self) -> str:
        return self.active_title

    def _show_active_content(self):
        if not hasattr(self, "content_area"):
            return
        palette = _GLOBAL_THEME.get_palette()
        for child in self.content_area.winfo_children():
            child.destroy()
        for title, btn in self.btn_map.items():
            if title == self.active_title:
                btn.config(bg=palette["accent"], fg=palette["accentText"])
            else:
                btn.config(bg=palette["surfaceSecondary"], fg=palette["foreground"])

        for title, content, _ in self.nav_items:
            if title == self.active_title:
                content._reset_widget_tree()
                w = content._realize(self.content_area)
                w.pack(fill="both", expand=True)
                break


class Table(GUIComponent):
    kind = "Table"

    def __init__(self, opts: Any = None):
        super().__init__()
        opts_dict = _normalize_dict(opts) if opts else {}
        self.columns = list(opts_dict.get("columns", ["Column 1"]))
        self.rows: List[List[Any]] = []
        self._tree: Optional[ttk.Treeview] = None

    def AddRow(self, row: List[Any]):
        self.rows.append(list(row))
        if self._tree is not None:
            self._tree.insert("", "end", values=row)
        return self

    def Clear(self):
        self.rows.clear()
        if self._tree is not None:
            for item in self._tree.get_children():
                self._tree.delete(item)
        return self

    def RemoveRow(self, index: int):
        if 0 <= index < len(self.rows):
            del self.rows[index]
            if self._tree is not None:
                children = self._tree.get_children()
                if 0 <= index < len(children):
                    self._tree.delete(children[index])
        return self

    def GetRows(self) -> List[List[Any]]:
        return self.rows

    def OnSelect(self, callback: Any):
        return self._register_event("select", callback)

    def _build(self, parent: tk.Widget) -> tk.Widget:
        frame = tk.Frame(parent)
        self._tree = ttk.Treeview(frame, columns=self.columns, show="headings")
        for col in self.columns:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=120)
        for row in self.rows:
            self._tree.insert("", "end", values=row)
        self._tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())

        scroll = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return frame

    def _on_tree_select(self):
        if self._tree is not None:
            selected = self._tree.selection()
            if selected:
                vals = self._tree.item(selected[0])["values"]
                self._dispatch_event("select", vals)


class List(GUIComponent):
    kind = "List"

    def __init__(self, items_or_opts: Any = None):
        super().__init__()
        self.items = []
        if isinstance(items_or_opts, (list, tuple)):
            self.items = [str(x) for x in items_or_opts]
        elif isinstance(items_or_opts, dict) or hasattr(items_or_opts, "properties"):
            opts = _normalize_dict(items_or_opts)
            self.items = [str(x) for x in opts.get("items", [])]
        self._listbox: Optional[tk.Listbox] = None

    def AddItem(self, item: str):
        self.items.append(str(item))
        if self._listbox is not None:
            self._listbox.insert("end", str(item))
        return self

    def RemoveItem(self, item: str):
        if str(item) in self.items:
            idx = self.items.index(str(item))
            del self.items[idx]
            if self._listbox is not None:
                self._listbox.delete(idx)
        return self

    def Clear(self):
        self.items.clear()
        if self._listbox is not None:
            self._listbox.delete(0, "end")
        return self

    def GetSelected(self) -> str:
        if self._listbox is not None:
            sel = self._listbox.curselection()
            if sel:
                return self.items[sel[0]]
        return ""

    def OnSelect(self, callback: Any):
        return self._register_event("select", callback)

    def _build(self, parent: tk.Widget) -> tk.Widget:
        palette = _GLOBAL_THEME.get_palette()
        frame = tk.Frame(parent, bg=palette["surface"])
        self._listbox = tk.Listbox(
            frame,
            bg=palette["inputBg"],
            fg=palette["foreground"],
            selectbackground=palette["accent"],
            selectforeground=palette["accentText"],
            bd=0,
            highlightthickness=1,
            highlightbackground=palette["border"],
        )
        for item in self.items:
            self._listbox.insert("end", item)
        self._listbox.bind("<<ListboxSelect>>", lambda e: self._dispatch_event("select", self.GetSelected()))
        self._listbox.pack(side="left", fill="both", expand=True)
        return frame


# ============================================================
# Menus & Toolbar
# ============================================================

class MenuBar:
    def __init__(self, root: tk.Tk = None):
        self.root = root
        self.menu = None

    def Add(self, title: str) -> "Menu":
        if self.menu is None and self.root is not None:
            self.menu = tk.Menu(self.root)
            self.root.config(menu=self.menu)
        sub = tk.Menu(self.menu, tearoff=0)
        if self.menu:
            self.menu.add_cascade(label=title, menu=sub)
        return Menu(sub)


class Menu:
    def __init__(self, tk_menu: tk.Menu):
        self.tk_menu = tk_menu
        self._interpreter = None

    def Add(self, label: str, callback: Any):
        def _cmd():
            if self._interpreter is not None:
                _invoke_callback(self._interpreter, callback, [])

        self.tk_menu.add_command(label=label, command=_cmd)
        return self

    def Separator(self):
        self.tk_menu.add_separator()
        return self


class ContextMenu(Menu):
    def __init__(self):
        super().__init__(tk.Menu(None, tearoff=0))

    def _show_popup(self, event):
        try:
            self.tk_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tk_menu.grab_release()


class Toolbar(Container):
    kind = "Toolbar"

    def AddButton(self, text: str, callback: Any, icon: str = None):
        btn = Button({"text": text, "icon": icon, "variant": "subtle"})
        btn.OnClick(callback)
        self.Add(btn)
        return btn


# ============================================================
# Dialog Helpers
# ============================================================

def Alert(title: str, message: str):
    messagebox.showinfo(str(title), str(message))


def Confirm(title: str, message: str) -> bool:
    return messagebox.askyesno(str(title), str(message))


def OpenFile(opts: Any = None) -> str:
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Open File")
    return filedialog.askopenfilename(title=title) or ""


def SaveFile(opts: Any = None) -> str:
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Save File")
    return filedialog.asksaveasfilename(title=title) or ""


def SelectFolder(opts: Any = None) -> str:
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Select Folder")
    return filedialog.askdirectory(title=title) or ""


# ============================================================
# Window Class
# ============================================================

class Window:
    def __init__(self, title_or_opts: Any, width: int = 800, height: int = 600):
        self.title = "BlazeLang GUI"
        self.width = 800
        self.height = 600
        self.theme = "system"
        self.centered = True
        self.resizable_x = True
        self.resizable_y = True
        self.min_width = None
        self.min_height = None
        self.max_width = None
        self.max_height = None
        self.icon_path = None

        if isinstance(title_or_opts, dict) or hasattr(title_or_opts, "properties"):
            opts = _normalize_dict(title_or_opts)
            self.title = str(opts.get("title", "BlazeLang GUI"))
            self.width = int(opts.get("width", 800))
            self.height = int(opts.get("height", 600))
            self.theme = opts.get("theme", "system")
            self.centered = bool(opts.get("centered", True))
            self.resizable_x = bool(opts.get("resizable", True))
            self.resizable_y = bool(opts.get("resizable", True))
            self.min_width = opts.get("minWidth", opts.get("minimumWidth"))
            self.min_height = opts.get("minHeight", opts.get("minimumHeight"))
            self.max_width = opts.get("maxWidth", opts.get("maximumWidth"))
            self.max_height = opts.get("maxHeight", opts.get("maximumHeight"))
            self.icon_path = opts.get("icon")
            _GLOBAL_THEME.set_theme(self.theme)
        else:
            self.title = str(title_or_opts)
            self.width = int(width)
            self.height = int(height)

        self.children: List[GUIComponent] = []
        self._root: Optional[tk.Tk] = None
        self._running = False
        self._destroyed = False
        self._style: Dict[str, Any] = {}
        self._callbacks: Dict[str, Any] = {}

    def _ensure_alive(self):
        if self._destroyed:
            raise _DestroyedError("Window")

    def SetTitle(self, title: str):
        self._ensure_alive()
        self.title = str(title)
        if self._root is not None:
            self._root.title(self.title)
        return self

    def GetTitle(self) -> str:
        return self.title

    def SetSize(self, width: int, height: int):
        self._ensure_alive()
        self.width = int(width)
        self.height = int(height)
        if self._root is not None:
            self._root.geometry(f"{self.width}x{self.height}")
        return self

    def GetSize(self) -> Tuple[int, int]:
        if self._root is not None:
            return (self._root.winfo_width(), self._root.winfo_height())
        return (self.width, self.height)

    def SetMinimumSize(self, width: int, height: int):
        self.min_width = int(width)
        self.min_height = int(height)
        if self._root is not None:
            self._root.minsize(self.min_width, self.min_height)
        return self

    SetMinSize = SetMinimumSize

    def SetMaximumSize(self, width: int, height: int):
        self.max_width = int(width)
        self.max_height = int(height)
        if self._root is not None:
            self._root.maxsize(self.max_width, self.max_height)
        return self

    SetMaxSize = SetMaximumSize

    def Center(self):
        if self._root is not None:
            self._root.update_idletasks()
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            x = (sw - self.width) // 2
            y = (sh - self.height) // 2
            self._root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        return self

    def Minimize(self):
        if self._root is not None:
            self._root.iconify()
        return self

    def Maximize(self):
        if self._root is not None:
            self._root.state("zoomed")
        return self

    def Restore(self):
        if self._root is not None:
            self._root.state("normal")
        return self

    def SetResizable(self, resizable: bool):
        self.resizable_x = bool(resizable)
        self.resizable_y = bool(resizable)
        if self._root is not None:
            self._root.resizable(self.resizable_x, self.resizable_y)
        return self

    def Resizable(self, width: bool, height: bool):
        self.resizable_x = bool(width)
        self.resizable_y = bool(height)
        if self._root is not None:
            self._root.resizable(self.resizable_x, self.resizable_y)
        return self

    def SetIcon(self, path: str):
        self.icon_path = str(path)
        if self._root is not None and os.path.isfile(self.icon_path):
            try:
                self._root.iconbitmap(self.icon_path)
            except Exception:
                pass
        return self

    # Events
    def OnClose(self, callback: Any):
        self._callbacks["close"] = callback
        return self

    def OnResize(self, callback: Any):
        self._callbacks["resize"] = callback
        return self

    def OnMove(self, callback: Any):
        self._callbacks["move"] = callback
        return self

    def OnMinimize(self, callback: Any):
        self._callbacks["minimize"] = callback
        return self

    def OnMaximize(self, callback: Any):
        self._callbacks["maximize"] = callback
        return self

    def Style(self, style: Any):
        self._ensure_alive()
        self._style.update(_normalize_dict(style))
        if self._root is not None:
            self._apply_style()
        return self

    SetStyle = Style
    UseStyle = Style

    def _apply_style(self):
        if self._root is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", self._style.get("bg", palette["background"]))
        _safe_config(self._root, "background", bg)
        _set_window_dark_titlebar(int(self._root.frame(), 16) if hasattr(self._root, "frame") else 0, palette["mode"] == "dark")

    def Add(self, *components: Any):
        self._ensure_alive()
        for comp in components:
            if isinstance(comp, (list, tuple)):
                self.Add(*comp)
                continue
            if isinstance(comp, MenuBar):
                comp.root = self._root
                continue
            if not isinstance(comp, GUIComponent):
                raise BlazeTypeError(f"Window.Add expects GUI components, got {type(comp).__name__}")
            comp._window = self
            self.children.append(comp)
            if self._root is not None:
                self._attach(comp)
        return self

    def _attach(self, component: GUIComponent):
        component._window = self
        widget = component._realize(self._root)
        widget.pack(fill="x", padx=4, pady=2)

    def _bind_interpreter(self, components: List[GUIComponent], interpreter):
        for component in components:
            component._interpreter = interpreter
            if hasattr(component, "_callbacks"):
                for cb in component._callbacks.values():
                    if hasattr(cb, "_interpreter"):
                        cb._interpreter = interpreter
            if isinstance(component, Container):
                self._bind_interpreter(component.children, interpreter)
            elif isinstance(component, NavigationView):
                for _, content_comp, _ in component.nav_items:
                    self._bind_interpreter([content_comp], interpreter)

    def Run(self, interpreter=None):
        self._ensure_alive()
        if self._running:
            raise BlazeRuntimeError("GUI window is already running", hint="Call app.Run() only once.")

        _set_windows_dpi_awareness()
        _set_windows_app_identity()

        self._root = tk.Tk()
        self._root.title(self.title)
        self._root.geometry(f"{self.width}x{self.height}")
        self._root.resizable(self.resizable_x, self.resizable_y)

        if self.min_width and self.min_height:
            self._root.minsize(self.min_width, self.min_height)
        if self.max_width and self.max_height:
            self._root.maxsize(self.max_width, self.max_height)

        if self.centered:
            self.Center()

        icon = self.icon_path or _get_gui_icon_path()
        if icon and os.path.isfile(icon):
            try:
                self._root.iconbitmap(default=icon)
                self._root.iconbitmap(icon)
            except Exception:
                try:
                    from PIL import Image as PILImage, ImageTk
                    icon_img = ImageTk.PhotoImage(PILImage.open(icon))
                    self._root.iconphoto(True, icon_img)
                except Exception:
                    pass

        palette = _GLOBAL_THEME.get_palette()
        _set_window_dark_titlebar(self._root.winfo_id(), palette["mode"] == "dark")
        self._apply_style()

        self._root.protocol("WM_DELETE_WINDOW", self.Close)
        self._bind_interpreter(self.children, interpreter)

        for component in self.children:
            self._attach(component)

        if "resize" in self._callbacks:
            self._root.bind("<Configure>", lambda e: self._dispatch_window_event("resize", e.width, e.height))

        self._running = True
        try:
            self._root.mainloop()
        except Exception as error:
            raise BlazeRuntimeError(f"GUI event loop error: {error}")
        finally:
            self._running = False

    def _dispatch_window_event(self, event_name: str, *args):
        cb = self._callbacks.get(event_name)
        if cb is not None and hasattr(self, "_interpreter") and self._interpreter is not None:
            try:
                _invoke_callback(self._interpreter, cb, list(args))
            except Exception:
                pass

    def Close(self):
        if self._destroyed:
            return
        if "close" in self._callbacks and hasattr(self, "_interpreter"):
            self._dispatch_window_event("close")
        self._running = False
        self._destroyed = True
        if self._root is not None:
            try:
                self._root.destroy()
            finally:
                self._root = None


# ============================================================
# Public Module Export Factory
# ============================================================

def create_gui_module(interpreter) -> Dict[str, Any]:

    def Create(title_or_opts: Any, width: int = 800, height: int = 600) -> Window:
        window = Window(title_or_opts, width, height)
        window._interpreter = interpreter
        orig_run = window.Run
        window.Run = lambda: orig_run(interpreter=interpreter)
        return window

    def SetTheme(theme_config: Any):
        _GLOBAL_THEME.set_theme(theme_config)

    def Theme(theme_config: Any):
        SetTheme(theme_config)

    def Style(values: Any = None) -> GUIStyle:
        return GUIStyle(values)

    return {
        "Create": Create,
        "Theme": Theme,
        "SetTheme": SetTheme,
        "Style": Style,

        # Widgets
        "Label": lambda t="": Label(t),
        "Text": lambda t="", opts=None: Text(t, opts),
        "Button": lambda t="": Button(t),
        "Input": lambda v="": Input(v),
        "PasswordInput": lambda v="": PasswordInput(v),
        "Checkbox": lambda t="": Checkbox(t),
        "CheckBox": lambda t="": Checkbox(t),
        "Toggle": lambda t="": Toggle(t),
        "Switch": lambda t="": Toggle(t),
        "Radio": lambda t="", g="default", v=None: Radio(t, g, v),
        "ComboBox": lambda items=None: ComboBox(items),
        "Slider": lambda min_val=0, max_val=100, val=50: Slider(min_val, max_val, val),
        "ProgressBar": lambda val=0: ProgressBar(val),
        "TextArea": lambda p="": TextArea(p),
        "Image": lambda s="": Image(s),
        "Video": lambda v="": VideoWidget(v),
        "Icon": lambda name="home", size=16: Icon(name, size),

        # Containers & Layouts
        "Card": lambda opts=None: Card(opts),
        "Container": lambda opts=None: Container(opts),
        "Panel": lambda opts=None: Panel(opts),
        "Row": lambda opts=None: Row(opts),
        "Column": lambda opts=None: Column(opts),
        "Stack": lambda opts=None: Stack(opts),
        "Grid": lambda opts=None: Grid(opts),
        "ScrollView": lambda opts=None: ScrollView(opts),
        "SplitView": lambda opts=None: SplitView(opts),
        "Spacer": lambda s=12: Spacer(s),
        "Divider": lambda o="horizontal": Divider(o),

        # Navigation & Views
        "Tabs": lambda: Tabs(),
        "NavigationView": lambda: NavigationView(),
        "Table": lambda opts=None: Table(opts),
        "List": lambda items=None: List(items),

        # Menus & Dialogs
        "MenuBar": lambda: MenuBar(),
        "ContextMenu": lambda: ContextMenu(),
        "Toolbar": lambda: Toolbar(),

        "Alert": Alert,
        "Confirm": Confirm,
        "OpenFile": OpenFile,
        "SaveFile": SaveFile,
        "SelectFolder": SelectFolder,
    }