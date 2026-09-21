"""
BlazeLang GUI 2.0 Module
Modern Windows 11 / Fluent Desktop UI Framework for BlazeLang powered by PySide6 / Qt.

Import:
    Import GUI from "gui"
"""

import os
import sys
import ctypes
from typing import Any, Dict, List, Optional, Tuple, Union

from PySide6.QtCore import Qt, QEvent, QObject, QSize
from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QImage,
    QFont,
    QColor,
    QAction,
    QPainter,
    QBrush,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QSlider,
    QProgressBar,
    QTextEdit,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QMenuBar,
    QMenu,
    QToolBar,
    QMessageBox,
    QFileDialog,
    QFrame,
    QSizePolicy,
)

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
# Qt Application Lifecycle Singleton Manager
# ============================================================

_QT_APP_INSTANCE: Optional[QApplication] = None


def _get_or_create_qapp() -> QApplication:
    """Safely obtain or initialize the Qt Application instance."""
    global _QT_APP_INSTANCE
    existing = QApplication.instance()
    if existing is not None:
        _QT_APP_INSTANCE = existing
        return existing

    _set_windows_dpi_awareness()
    _set_windows_app_identity()

    app = QApplication(sys.argv if sys.argv else ["BlazeLang"])
    app.setApplicationName("BlazeLang GUI")
    app.setOrganizationName("BlazeLang")
    _QT_APP_INSTANCE = app
    return app


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
                if "mode" in self.custom_overrides:
                    self.custom_overrides["mode"] = val
            else:
                raise BlazeValueError(f"Invalid theme mode '{theme_config}'. Use 'system', 'light', or 'dark'.")
        elif isinstance(theme_config, dict) or hasattr(theme_config, "properties"):
            normalized = _normalize_dict(theme_config)
            if "mode" in normalized:
                self.mode = str(normalized["mode"]).lower()
            self.custom_overrides.update(normalized)
        else:
            raise BlazeTypeError("SetTheme expects a string or style dictionary")

        # Dynamically refresh active windows
        for win in list(Window._ACTIVE_WINDOWS):
            if win._window_widget is not None and not win._destroyed:
                try:
                    win._apply_style()
                except Exception:
                    pass


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


def _parse_font(style: Dict[str, Any], palette: Dict[str, Any]) -> QFont:
    font_val = style.get("font")
    family = style.get("font_family", style.get("fontFamily", palette.get("fontFamily", "Segoe UI")))
    size = style.get("font_size", style.get("fontSize", palette.get("fontSize", 10)))
    weight = style.get("font_weight", style.get("fontWeight", "normal"))
    bold = style.get("bold", False) or (weight in ("bold", "semibold"))
    italic = style.get("italic", False)

    if isinstance(font_val, (int, float)):
        size = int(font_val)
    elif isinstance(font_val, str):
        parts = font_val.split()
        if parts:
            family = parts[0]
            if len(parts) > 1 and parts[1].isdigit():
                size = int(parts[1])

    try:
        size = int(size)
    except Exception:
        size = 10

    qfont = QFont(str(family), size)
    if bold:
        qfont.setBold(True)
    if italic:
        qfont.setItalic(True)
    return qfont


def _safe_config(widget: QWidget, option: str, value: Any):
    """Compatibility helper mimicking legacy widget option assignment."""
    if widget is None or value is None:
        return
    try:
        if option in ("background", "bg"):
            p = widget.palette()
            p.setColor(widget.backgroundRole(), QColor(str(value)))
            widget.setPalette(p)
        elif option in ("foreground", "fg"):
            p = widget.palette()
            p.setColor(widget.foregroundRole(), QColor(str(value)))
            widget.setPalette(p)
        elif option == "state":
            widget.setEnabled(value != "disabled")
        elif option == "width":
            widget.setFixedWidth(int(value))
        elif option == "height":
            widget.setFixedHeight(int(value))
    except Exception:
        pass


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
# Event Filter Helper for Qt Widgets
# ============================================================

class _QtEventFilter(QObject):
    """Handles hover, focus, blur, and keyboard events cleanly on Qt widgets."""

    def __init__(self, component: "GUIComponent"):
        super().__init__()
        self._comp = component

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._comp._destroyed:
            return False

        etype = event.type()
        if etype == QEvent.Type.Enter:
            self._comp._dispatch_event("hover", True)
        elif etype == QEvent.Type.Leave:
            self._comp._dispatch_event("hover", False)
        elif etype == QEvent.Type.FocusIn:
            self._comp._dispatch_event("focus")
        elif etype == QEvent.Type.FocusOut:
            self._comp._dispatch_event("blur")
        elif etype == QEvent.Type.KeyPress:
            key_text = event.text() or event.keyCombination().key().name
            self._comp._dispatch_event("keyDown", key_text)
        elif etype == QEvent.Type.KeyRelease:
            key_text = event.text() or event.keyCombination().key().name
            self._comp._dispatch_event("keyUp", key_text)
        elif etype == QEvent.Type.MouseButtonDblClick:
            self._comp._dispatch_event("doubleClick")
        elif etype == QEvent.Type.ContextMenu:
            if "contextMenu" in self._comp._callbacks:
                menu = self._comp._callbacks["contextMenu"]
                menu._show_popup(event.globalPos())
                return True

        return super().eventFilter(watched, event)


# ============================================================
# Component Base Class
# ============================================================

class GUIComponent:
    """Base class for all BlazeLang GUI components."""
    kind = "Component"

    def __init__(self):
        self._widget: Optional[QWidget] = None
        self._window: Optional["Window"] = None
        self._destroyed = False
        self._visible = True
        self._enabled = True
        self._style: Dict[str, Any] = {}
        self._callbacks: Dict[str, Any] = {}
        self._interpreter = None
        self._event_filter: Optional[_QtEventFilter] = None

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
            self._widget.show()
        return self

    def Hide(self):
        self._ensure_alive()
        self._visible = False
        if self._widget is not None:
            self._widget.hide()
        return self

    def SetVisible(self, visible: bool):
        return self.Show() if visible else self.Hide()

    def Enable(self):
        self._ensure_alive()
        self._enabled = True
        if self._widget is not None:
            self._widget.setEnabled(True)
        return self

    def Disable(self):
        self._ensure_alive()
        self._enabled = False
        if self._widget is not None:
            self._widget.setEnabled(False)
        return self

    def SetEnabled(self, enabled: bool):
        return self.Enable() if enabled else self.Disable()

    def Focus(self):
        self._ensure_alive()
        if self._widget is not None:
            self._widget.setFocus()
        return self

    # --------------------------------------------------------
    # Geometry Helpers
    # --------------------------------------------------------

    def SetWidth(self, width: Any):
        self._style["width"] = width
        if self._widget is not None and isinstance(width, (int, float)):
            self._widget.setFixedWidth(int(width))
        return self

    def SetHeight(self, height: Any):
        self._style["height"] = height
        if self._widget is not None and isinstance(height, (int, float)):
            self._widget.setFixedHeight(int(height))
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

    def _realize(self, parent: Optional[QWidget]) -> QWidget:
        self._ensure_alive()
        if self._widget is None:
            self._widget = self._build(parent)
            self._widget.setEnabled(self._enabled)
            self._widget.setVisible(self._visible)
            self._apply_style()
            self._bind_events()
        return self._widget

    def _bind_events(self):
        if self._widget is None:
            return
        if self._event_filter is None:
            self._event_filter = _QtEventFilter(self)
            self._widget.installEventFilter(self._event_filter)

    def _apply_style(self):
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        style = self._style

        qfont = _parse_font(style, palette)
        self._widget.setFont(qfont)

        width = style.get("width")
        height = style.get("height")
        if width is not None and isinstance(width, (int, float)):
            self._widget.setFixedWidth(int(width))
        if height is not None and isinstance(height, (int, float)):
            self._widget.setFixedHeight(int(height))


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        lbl = QLabel(self.text, parent)
        lbl.setWordWrap(True)
        self._apply_alignment(lbl)
        return lbl

    def _apply_alignment(self, lbl: QLabel):
        align_map = {
            "center": Qt.AlignmentFlag.AlignCenter,
            "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        }
        align = align_map.get(self._style.get("alignment", "left"), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lbl.setAlignment(align)

    def SetText(self, text: str):
        self._ensure_alive()
        self.text = str(text)
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._widget.setText(self.text)
        return self

    def GetText(self) -> str:
        return self.text

    def SetFontSize(self, size: int):
        return self.SetStyleValue("fontSize", size)

    def SetFontWeight(self, weight: str):
        return self.SetStyleValue("fontWeight", weight)

    def SetAlignment(self, alignment: str):
        self.SetStyleValue("alignment", alignment)
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._apply_alignment(self._widget)
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        fg = self._style.get("foreground", self._style.get("color", palette["foreground"]))
        self._widget.setStyleSheet(f"color: {fg}; background: transparent;")


class Text(Label):
    kind = "Text"


# ============================================================
# Icon Component
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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        glyph = self.ICON_MAP.get(self.name.lower(), self.name)
        lbl = QLabel(glyph, parent)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI Symbol", self.size)
        lbl.setFont(font)
        return lbl

    def _apply_style(self):
        super()._apply_style()
        if self._widget is not None:
            palette = _GLOBAL_THEME.get_palette()
            fg = self._style.get("foreground", palette["foreground"])
            self._widget.setStyleSheet(f"color: {fg}; background: transparent;")


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

    def _get_display_text(self) -> str:
        if self.icon:
            glyph = Icon.ICON_MAP.get(str(self.icon).lower(), str(self.icon))
            return f"{glyph}  {self.text}"
        return self.text

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        btn = QPushButton(self._get_display_text(), parent)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_click_cmd)
        return btn

    def SetText(self, text: str):
        self._ensure_alive()
        self.text = str(text)
        if self._widget is not None and isinstance(self._widget, QPushButton):
            self._widget.setText(self._get_display_text())
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
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        variant = self._style.get("variant", self.variant)
        radius = self._style.get("radius", palette.get("radius", 6))

        bg = palette["surfaceSecondary"]
        fg = palette["foreground"]
        hover_bg = palette["surfaceTertiary"]
        pressed_bg = palette["surfaceTertiary"]
        border = palette["border"]

        if variant == "primary":
            bg = palette["accent"]
            fg = palette["accentText"]
            hover_bg = palette["accentHover"]
            pressed_bg = palette["accentPressed"]
            border = "transparent"
        elif variant == "danger":
            bg = palette["danger"]
            fg = "#ffffff"
            hover_bg = palette["dangerHover"]
            pressed_bg = palette["dangerHover"]
            border = "transparent"
        elif variant == "success":
            bg = palette["success"]
            fg = "#ffffff"
            hover_bg = palette["success"]
            pressed_bg = palette["success"]
            border = "transparent"
        elif variant == "outline":
            bg = "transparent"
            fg = palette["foreground"]
            hover_bg = palette["surfaceSecondary"]
            pressed_bg = palette["surfaceTertiary"]
            border = palette["border"]
        elif variant == "subtle":
            bg = "transparent"
            fg = palette["foreground"]
            hover_bg = palette["surfaceSecondary"]
            pressed_bg = palette["surfaceTertiary"]
            border = "transparent"

        bg = self._style.get("background", self._style.get("bg", bg))
        fg = self._style.get("foreground", self._style.get("color", fg))

        height_rule = ""
        height = self._style.get("height")
        if height is not None and isinstance(height, (int, float)):
            height_rule = f"min-height: {int(height)}px; max-height: {int(height)}px;"

        qss = f"""
        QPushButton {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: 6px 14px;
            font-family: "{palette.get('fontFamily', 'Segoe UI')}";
            {height_rule}
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
        QPushButton:pressed {{
            background-color: {pressed_bg};
        }}
        QPushButton:disabled {{
            background-color: {palette['surfaceTertiary']};
            color: {palette['foregroundSecondary']};
            border-color: {palette['border']};
        }}
        """
        self._widget.setStyleSheet(qss)


# ============================================================
# Input Components (Input, PasswordInput)
# ============================================================

class Input(GUIComponent):
    kind = "Input"
    _is_password = False

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

        self._changing = False

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        entry = QLineEdit(self.initial_value, parent)
        if self.placeholder:
            entry.setPlaceholderText(self.placeholder)
        if self.readonly:
            entry.setReadOnly(True)

        align_map = {
            "center": Qt.AlignmentFlag.AlignCenter,
            "right": Qt.AlignmentFlag.AlignRight,
            "left": Qt.AlignmentFlag.AlignLeft,
        }
        align = align_map.get(self._style.get("alignment", "left"), Qt.AlignmentFlag.AlignLeft)
        entry.setAlignment(align)

        if self._is_password:
            entry.setEchoMode(QLineEdit.EchoMode.Password)
            self._setup_password_action(entry)

        entry.textChanged.connect(self._on_text_changed)
        entry.returnPressed.connect(lambda: self._dispatch_event("submit", self.GetValue()))
        return entry

    def _setup_password_action(self, entry: QLineEdit):
        action = QAction("👁", entry)
        entry.addAction(action, QLineEdit.ActionPosition.TrailingPosition)
        showing = [False]

        def toggle():
            showing[0] = not showing[0]
            entry.setEchoMode(QLineEdit.EchoMode.Normal if showing[0] else QLineEdit.EchoMode.Password)

        action.triggered.connect(toggle)

    def _on_text_changed(self, text: str):
        if not self._changing:
            self._dispatch_event("change", text)

    def GetValue(self) -> str:
        self._ensure_alive()
        if self._widget is not None and isinstance(self._widget, QLineEdit):
            return self._widget.text()
        return self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._widget is not None and isinstance(self._widget, QLineEdit):
            self._changing = True
            try:
                self._widget.setText(self.initial_value)
            finally:
                self._changing = False
        return self

    def SetPlaceholder(self, placeholder: str):
        self.placeholder = str(placeholder)
        if self._widget is not None and isinstance(self._widget, QLineEdit):
            self._widget.setPlaceholderText(self.placeholder)
        return self

    def SetReadOnly(self, readonly: bool):
        self.readonly = bool(readonly)
        if self._widget is not None and isinstance(self._widget, QLineEdit):
            self._widget.setReadOnly(self.readonly)
        return self

    def Clear(self):
        return self.SetValue("")

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        radius = self._style.get("radius", palette.get("radius", 6))
        bg = palette["inputBg"]
        fg = palette["foreground"]
        border = palette["inputBorder"]
        focus_border = palette["inputFocusBorder"]

        qss = f"""
        QLineEdit {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: {radius}px;
            padding: 6px 8px;
            selection-background-color: {palette['accent']};
            selection-color: {palette['accentText']};
        }}
        QLineEdit:focus {{
            border: 2px solid {focus_border};
        }}
        QLineEdit:read-only {{
            background-color: {palette['surfaceSecondary']};
        }}
        """
        self._widget.setStyleSheet(qss)


class PasswordInput(Input):
    kind = "PasswordInput"
    _is_password = True

    def __init__(self, val_or_opts: Any = ""):
        super().__init__(val_or_opts)
        self.reveal_enabled = True


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        cb = QCheckBox(self.text, parent)
        cb.setChecked(self.initial_checked)
        cb.toggled.connect(lambda val: self._dispatch_event("change", val))
        return cb

    def IsChecked(self) -> bool:
        self._ensure_alive()
        if self._widget is not None and isinstance(self._widget, QCheckBox):
            return self._widget.isChecked()
        return self.initial_checked

    def SetChecked(self, value: bool):
        self._ensure_alive()
        self.initial_checked = bool(value)
        if self._widget is not None and isinstance(self._widget, QCheckBox):
            self._widget.setChecked(self.initial_checked)
        return self

    def SetText(self, text: str):
        self.text = str(text)
        if self._widget is not None and isinstance(self._widget, QCheckBox):
            self._widget.setText(self.text)
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        fg = palette["foreground"]
        qss = f"""
        QCheckBox {{
            color: {fg};
            spacing: 8px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid {palette['border']};
            background-color: {palette['surface']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {palette['accent']};
            border-color: {palette['accent']};
        }}
        """
        self._widget.setStyleSheet(qss)


CheckBox = Checkbox


class _QtToggleSwitch(QWidget):
    """Modern Windows 11 pill toggle switch implementation."""

    def __init__(self, text: str = "", checked: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._text = text
        self._checked = checked
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.update()

    def setText(self, text: str):
        self._text = text
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update()
            if hasattr(self, "_on_toggle"):
                self._on_toggle(self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        palette = _GLOBAL_THEME.get_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw pill track
        track_w, track_h = 40, 20
        track_y = (self.height() - track_h) // 2
        bg_col = QColor(palette["accent"] if self._checked else palette["surfaceTertiary"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(0, track_y, track_w, track_h, track_h // 2, track_h // 2)

        # Draw knob
        knob_dia = 14
        knob_y = track_y + (track_h - knob_dia) // 2
        knob_x = track_w - knob_dia - 3 if self._checked else 3
        knob_col = QColor(palette["accentText"] if self._checked else palette["foregroundSecondary"])
        painter.setBrush(QBrush(knob_col))
        painter.drawEllipse(knob_x, knob_y, knob_dia, knob_dia)

        # Draw label text
        if self._text:
            painter.setPen(QPen(QColor(palette["foreground"])))
            painter.setFont(self.font())
            painter.drawText(track_w + 10, self.height() // 2 + 5, self._text)


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        widget = _QtToggleSwitch(self.text, self.checked, parent)
        widget._on_toggle = self._on_toggled
        return widget

    def _on_toggled(self, checked: bool):
        self.checked = checked
        self._dispatch_event("change", self.checked)

    def toggle(self):
        self.SetChecked(not self.checked)
        self._dispatch_event("change", self.checked)

    def IsChecked(self) -> bool:
        if self._widget is not None and isinstance(self._widget, _QtToggleSwitch):
            return self._widget.isChecked()
        return self.checked

    def SetChecked(self, value: bool):
        self.checked = bool(value)
        if self._widget is not None and isinstance(self._widget, _QtToggleSwitch):
            self._widget.setChecked(self.checked)
        return self


Switch = Toggle


class Radio(GUIComponent):
    kind = "Radio"
    _GROUPS: Dict[str, QButtonGroup] = {}
    _INITIAL_GROUPS: Dict[str, str] = {}

    def __init__(self, text: str = "", group: str = "default", value: str = None):
        super().__init__()
        self.text = text
        self.group = group
        self.value = value if value is not None else text

    @classmethod
    def _get_group(cls, group: str) -> QButtonGroup:
        if group not in cls._GROUPS:
            cls._GROUPS[group] = QButtonGroup()
        return cls._GROUPS[group]

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        rb = QRadioButton(self.text, parent)
        group_obj = self._get_group(self.group)
        group_obj.addButton(rb)
        if not hasattr(group_obj, "_val_map"):
            group_obj._val_map = {}
        group_obj._val_map[rb] = self.value

        initial = Radio._INITIAL_GROUPS.get(self.group)
        if initial is not None and initial == self.value:
            rb.setChecked(True)

        rb.toggled.connect(self._on_toggled)
        return rb

    def _on_toggled(self, checked: bool):
        if checked:
            Radio._INITIAL_GROUPS[self.group] = self.value
            self._dispatch_event("change", self.GetValue())

    def IsChecked(self) -> bool:
        if self._widget is not None and isinstance(self._widget, QRadioButton):
            return self._widget.isChecked()
        return Radio._INITIAL_GROUPS.get(self.group) == self.value

    def SetChecked(self, checked: bool):
        if checked:
            Radio._INITIAL_GROUPS[self.group] = self.value
            if self._widget is not None and isinstance(self._widget, QRadioButton):
                self._widget.setChecked(True)
        return self

    def GetValue(self) -> str:
        if self._widget is not None and isinstance(self._widget, QRadioButton):
            group_obj = self._get_group(self.group)
            checked_btn = group_obj.checkedButton()
            if checked_btn is not None and hasattr(group_obj, "_val_map"):
                return group_obj._val_map.get(checked_btn, Radio._INITIAL_GROUPS.get(self.group, ""))
        return Radio._INITIAL_GROUPS.get(self.group, "")

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        qss = f"""
        QRadioButton {{
            color: {palette['foreground']};
            spacing: 8px;
            background: transparent;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 9px;
            border: 1px solid {palette['border']};
            background-color: {palette['surface']};
        }}
        QRadioButton::indicator:checked {{
            background-color: {palette['accent']};
            border-color: {palette['accent']};
        }}
        """
        self._widget.setStyleSheet(qss)


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

        self._changing = False

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        combo = QComboBox(parent)
        for item in self.items:
            combo.addItem(item)

        if self.initial_value:
            combo.setCurrentText(self.initial_value)

        combo.currentTextChanged.connect(self._on_selection_changed)
        return combo

    def _on_selection_changed(self, text: str):
        if not self._changing:
            self._dispatch_event("change", text)

    def GetValue(self) -> str:
        self._ensure_alive()
        if self._widget is not None and isinstance(self._widget, QComboBox):
            return self._widget.currentText()
        return self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._widget is not None and isinstance(self._widget, QComboBox):
            self._changing = True
            try:
                self._widget.setCurrentText(self.initial_value)
            finally:
                self._changing = False
        return self

    def AddItem(self, item: str):
        self.items.append(str(item))
        if self._widget is not None and isinstance(self._widget, QComboBox):
            self._widget.addItem(str(item))
        return self

    def RemoveItem(self, item: str):
        if str(item) in self.items:
            self.items.remove(str(item))
            if self._widget is not None and isinstance(self._widget, QComboBox):
                idx = self._widget.findText(str(item))
                if idx >= 0:
                    self._widget.removeItem(idx)
        return self

    def Clear(self):
        self.items.clear()
        if self._widget is not None and isinstance(self._widget, QComboBox):
            self._widget.clear()
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        radius = self._style.get("radius", palette.get("radius", 6))
        qss = f"""
        QComboBox {{
            background-color: {palette['inputBg']};
            color: {palette['foreground']};
            border: 1px solid {palette['inputBorder']};
            border-radius: {radius}px;
            padding: 6px 12px;
        }}
        QComboBox:focus {{
            border: 2px solid {palette['inputFocusBorder']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {palette['surface']};
            color: {palette['foreground']};
            selection-background-color: {palette['accent']};
            selection-color: {palette['accentText']};
            border: 1px solid {palette['border']};
        }}
        """
        self._widget.setStyleSheet(qss)


class Slider(GUIComponent):
    kind = "Slider"

    def __init__(self, min_or_opts: Any = 0, max_val: float = 100, val: float = 50):
        super().__init__()
        self.min = 0.0
        self.max = 100.0
        self.value = 50.0

        if isinstance(min_or_opts, dict) or hasattr(min_or_opts, "properties"):
            opts = _normalize_dict(min_or_opts)
            self.min = float(opts.get("min", 0))
            self.max = float(opts.get("max", 100))
            self.value = float(opts.get("value", 50))
        else:
            self.min = float(min_or_opts)
            self.max = float(max_val)
            self.value = float(val)

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        slider = QSlider(Qt.Orientation.Horizontal, parent)
        slider.setRange(int(self.min), int(self.max))
        slider.setValue(int(self.value))
        slider.valueChanged.connect(lambda v: self._dispatch_event("change", float(v)))
        return slider

    def GetValue(self) -> float:
        self._ensure_alive()
        if self._widget is not None and isinstance(self._widget, QSlider):
            return float(self._widget.value())
        return self.value

    def SetValue(self, value: float):
        self._ensure_alive()
        self.value = float(value)
        if self._widget is not None and isinstance(self._widget, QSlider):
            self._widget.setValue(int(self.value))
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        qss = f"""
        QSlider::groove:horizontal {{
            border: none;
            height: 4px;
            background: {palette['surfaceTertiary']};
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {palette['accent']};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {palette['accent']};
            border: 2px solid {palette['surface']};
            width: 16px;
            margin-top: -6px;
            margin-bottom: -6px;
            border-radius: 8px;
        }}
        """
        self._widget.setStyleSheet(qss)


class ProgressBar(GUIComponent):
    kind = "ProgressBar"

    def __init__(self, val_or_opts: Any = 0):
        super().__init__()
        self.value = 0.0
        if isinstance(val_or_opts, dict) or hasattr(val_or_opts, "properties"):
            opts = _normalize_dict(val_or_opts)
            self.value = float(opts.get("value", 0))
        else:
            self.value = float(val_or_opts)

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        bar = QProgressBar(parent)
        bar.setRange(0, 100)
        bar.setValue(int(self.value))
        bar.setTextVisible(False)
        return bar

    def SetValue(self, value: float):
        self._ensure_alive()
        self.value = float(value)
        if self._widget is not None and isinstance(self._widget, QProgressBar):
            self._widget.setValue(int(self.value))
        return self

    def SetIndeterminate(self, indeterminate: bool):
        if self._widget is not None and isinstance(self._widget, QProgressBar):
            if indeterminate:
                self._widget.setRange(0, 0)
            else:
                self._widget.setRange(0, 100)
                self._widget.setValue(int(self.value))
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        radius = palette.get("radius", 6)
        qss = f"""
        QProgressBar {{
            background-color: {palette['surfaceTertiary']};
            border-radius: {radius}px;
            max-height: 6px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {palette['accent']};
            border-radius: {radius}px;
        }}
        """
        self._widget.setStyleSheet(qss)


class TextArea(GUIComponent):
    kind = "TextArea"

    def __init__(self, placeholder_or_opts: Any = ""):
        super().__init__()
        self.placeholder = ""
        self.wrap = True
        self.initial_value = ""

        if isinstance(placeholder_or_opts, dict) or hasattr(placeholder_or_opts, "properties"):
            opts = _normalize_dict(placeholder_or_opts)
            self.placeholder = str(opts.get("placeholder", ""))
            self.initial_value = str(opts.get("value", ""))
            self.wrap = bool(opts.get("wrap", True))
        else:
            self.placeholder = str(placeholder_or_opts)

        self._changing = False

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        text_edit = QTextEdit(parent)
        if self.placeholder:
            text_edit.setPlaceholderText(self.placeholder)
        if self.initial_value:
            text_edit.setPlainText(self.initial_value)

        text_edit.setLineWrapMode(
            QTextEdit.LineWrapMode.WidgetWidth if self.wrap else QTextEdit.LineWrapMode.NoWrap
        )
        text_edit.textChanged.connect(self._on_text_changed)
        return text_edit

    def _on_text_changed(self):
        if not self._changing:
            self._dispatch_event("change", self.GetValue())

    def GetValue(self) -> str:
        self._ensure_alive()
        if self._widget is not None and isinstance(self._widget, QTextEdit):
            return self._widget.toPlainText()
        return self.initial_value

    def SetValue(self, value: str):
        self._ensure_alive()
        self.initial_value = str(value)
        if self._widget is not None and isinstance(self._widget, QTextEdit):
            self._changing = True
            try:
                self._widget.setPlainText(self.initial_value)
            finally:
                self._changing = False
        return self

    def Append(self, text: str):
        self._ensure_alive()
        self.initial_value += str(text)
        if self._widget is not None and isinstance(self._widget, QTextEdit):
            self._widget.append(str(text))
        return self

    def Clear(self):
        return self.SetValue("")

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        radius = self._style.get("radius", palette.get("radius", 6))
        qss = f"""
        QTextEdit {{
            background-color: {palette['inputBg']};
            color: {palette['foreground']};
            border: 1px solid {palette['inputBorder']};
            border-radius: {radius}px;
            padding: 8px;
            selection-background-color: {palette['accent']};
            selection-color: {palette['accentText']};
        }}
        QTextEdit:focus {{
            border: 2px solid {palette['inputFocusBorder']};
        }}
        """
        self._widget.setStyleSheet(qss)


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        lbl = QLabel(parent)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_image(lbl)
        return lbl

    def _update_image(self, lbl: QLabel):
        if not self.source:
            return
        try:
            pixmap = None

            # Case 1: BlazeImage or object wrapping PIL image
            if hasattr(self.source, "_image"):
                from PIL import ImageQt
                qimg = ImageQt.ImageQt(self.source._image)
                pixmap = QPixmap.fromImage(qimg)

            # Case 2: BlazeVideo object
            elif hasattr(self.source, "AddListener") and callable(getattr(self.source, "AddListener", None)):
                def on_frame(frame):
                    try:
                        from PIL import ImageQt
                        qimg = ImageQt.ImageQt(frame)
                        pix = QPixmap.fromImage(qimg)
                        if self.req_width and self.req_height:
                            pix = pix.scaled(int(self.req_width), int(self.req_height), Qt.AspectRatioMode.KeepAspectRatio)
                        lbl.setPixmap(pix)
                    except Exception:
                        pass

                self.source.AddListener(on_frame)
                if hasattr(self.source, "_bind_widget"):
                    self.source._bind_widget(lbl)
                frame = self.source.GetFrame()
                if frame is not None:
                    from PIL import ImageQt
                    qimg = ImageQt.ImageQt(frame)
                    pixmap = QPixmap.fromImage(qimg)

            # Case 3: File path
            elif isinstance(self.source, str) and os.path.isfile(self.source):
                pixmap = QPixmap(self.source)

            if pixmap is not None and not pixmap.isNull():
                if self.req_width and self.req_height:
                    aspect_mode = (
                        Qt.AspectRatioMode.KeepAspectRatio
                        if self.stretch == "contain"
                        else Qt.AspectRatioMode.IgnoreAspectRatio
                    )
                    pixmap = pixmap.scaled(int(self.req_width), int(self.req_height), aspect_mode)
                lbl.setPixmap(pixmap)
        except Exception:
            pass

    def SetSource(self, source: Any):
        self.source = source
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._update_image(self._widget)
        return self

    def SetSize(self, width: int, height: int):
        self.req_width = width
        self.req_height = height
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._update_image(self._widget)
        return self

    def SetStretch(self, stretch: str):
        self.stretch = stretch
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._update_image(self._widget)
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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        lbl = QLabel(parent)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._attach_video(lbl)
        return lbl

    def _attach_video(self, lbl: QLabel):
        if self.video is None:
            return

        def on_frame(pil_img):
            try:
                from PIL import ImageQt
                qimg = ImageQt.ImageQt(pil_img)
                pixmap = QPixmap.fromImage(qimg)
                if self.req_width and self.req_height:
                    pixmap = pixmap.scaled(int(self.req_width), int(self.req_height), Qt.AspectRatioMode.KeepAspectRatio)
                lbl.setPixmap(pixmap)
            except Exception:
                pass

        if hasattr(self.video, "AddListener"):
            self.video.AddListener(on_frame)
            if hasattr(self.video, "_bind_widget"):
                self.video._bind_widget(lbl)

    def SetVideo(self, video: Any):
        self.video = video
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._attach_video(self._widget)
        return self

    def SetSource(self, source: Any):
        return self.SetVideo(source)

    def SetSize(self, width: int, height: int):
        self.req_width = width
        self.req_height = height
        if self._widget is not None and isinstance(self._widget, QLabel):
            self._attach_video(self._widget)
        return self


# ============================================================
# Containers & Layout Components
# ============================================================

class Container(GUIComponent):
    kind = "Container"
    _layout_type = "vertical"

    def __init__(self, opts: Any = None):
        super().__init__()
        self.children: List[GUIComponent] = []
        self._layout: Optional[Union[QVBoxLayout, QHBoxLayout]] = None
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
            if self._widget is not None and self._layout is not None:
                self._attach_child(comp)
        return self

    def Remove(self, component: GUIComponent):
        self._ensure_alive()
        if component in self.children:
            self.children.remove(component)
            if component._widget is not None:
                if self._layout is not None:
                    self._layout.removeWidget(component._widget)
                component._widget.deleteLater()
                component._widget = None
        return self

    def Clear(self):
        self._ensure_alive()
        for child in list(self.children):
            self.Remove(child)
        return self

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        frame = QFrame(parent)
        if self._layout_type == "horizontal":
            self._layout = QHBoxLayout(frame)
        else:
            self._layout = QVBoxLayout(frame)

        pad = int(self._style.get("padding", 4))
        self._layout.setContentsMargins(pad, pad, pad, pad)
        self._layout.setSpacing(int(self._style.get("spacing", 4)))
        return frame

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        w = component._realize(self._widget)
        if self._layout is not None:
            self._layout.addWidget(w)

    def _realize(self, parent: Optional[QWidget]) -> QWidget:
        widget = super()._realize(parent)
        for child in self.children:
            self._attach_child(child)
        return widget

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", self._style.get("bg", palette["surface"]))
        border = self._style.get("border", "transparent")
        radius = self._style.get("radius", 0)

        qss = f"""
        QFrame {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}
        """
        self._widget.setStyleSheet(qss)


class Panel(Container):
    kind = "Panel"
    _layout_type = "vertical"


class Column(Container):
    kind = "Column"
    _layout_type = "vertical"


class Row(Container):
    kind = "Row"
    _layout_type = "horizontal"


class Stack(Container):
    kind = "Stack"

    def __init__(self, opts: Any = None):
        super().__init__(opts)
        opts_dict = _normalize_dict(opts) if opts else {}
        direction = opts_dict.get("direction", "vertical")
        self._layout_type = "horizontal" if direction == "horizontal" else "vertical"


class Card(Container):
    kind = "Card"
    _layout_type = "vertical"

    def SetRadius(self, radius: int):
        self._style["radius"] = radius
        if self._widget is not None:
            self._apply_style()
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", palette["cardBg"])
        border = self._style.get("border", palette["cardBorder"])
        radius = self._style.get("radius", palette.get("radius", 8))

        qss = f"""
        QFrame {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: {radius}px;
        }}
        """
        self._widget.setStyleSheet(qss)


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
        self._grid_layout: Optional[QGridLayout] = None

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

        if self._widget is not None and self._grid_layout is not None:
            self._attach_child(component)
        return self

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        frame = QFrame(parent)
        self._grid_layout = QGridLayout(frame)
        self._grid_layout.setSpacing(self.spacing)
        pad = int(self._style.get("padding", 4))
        self._grid_layout.setContentsMargins(pad, pad, pad, pad)
        return frame

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        w = component._realize(self._widget)
        r, c, rs, cs = self.grid_positions.get(component, (0, 0, 1, 1))
        if self._grid_layout is not None:
            self._grid_layout.addWidget(w, r, c, rs, cs)


class ScrollView(Container):
    kind = "ScrollView"

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        inner_frame = QFrame()
        self._layout = QVBoxLayout(inner_frame)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(inner_frame)
        self._inner_frame = inner_frame
        return scroll_area

    def _attach_child(self, component: GUIComponent):
        component._window = self._window
        w = component._realize(self._inner_frame)
        if self._layout is not None:
            self._layout.addWidget(w)


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        orient = Qt.Orientation.Horizontal if self.orientation == "horizontal" else Qt.Orientation.Vertical
        splitter = QSplitter(orient, parent)
        if self.left_comp:
            w1 = self.left_comp._realize(splitter)
            splitter.addWidget(w1)
        if self.right_comp:
            w2 = self.right_comp._realize(splitter)
            splitter.addWidget(w2)

        total = 1000
        left_size = int(total * self.ratio)
        right_size = total - left_size
        splitter.setSizes([left_size, right_size])
        return splitter


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

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        w = QWidget(parent)
        if self.expand:
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            w.setFixedSize(self.size, self.size)
        return w


class Divider(GUIComponent):
    kind = "Divider"

    def __init__(self, orient: str = "horizontal"):
        super().__init__()
        self.orient = orient

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        line = QFrame(parent)
        if self.orient == "horizontal":
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFixedHeight(1)
        else:
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFixedWidth(1)
        return line

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        self._widget.setStyleSheet(f"background-color: {palette['border']}; border: none;")


# ============================================================
# Advanced Navigation & Data Views (Tabs, Navigation, Table, List)
# ============================================================

class Tabs(GUIComponent):
    kind = "Tabs"

    def __init__(self):
        super().__init__()
        self.tabs_map: Dict[str, Container] = {}
        self._tab_widget: Optional[QTabWidget] = None

    def Add(self, title: str) -> Container:
        panel = Container()
        self.tabs_map[title] = panel
        if self._tab_widget is not None:
            w = panel._realize(self._tab_widget)
            self._tab_widget.addTab(w, title)
        return panel

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        self._tab_widget = QTabWidget(parent)
        for title, panel in self.tabs_map.items():
            w = panel._realize(self._tab_widget)
            self._tab_widget.addTab(w, title)
        self._tab_widget.currentChanged.connect(lambda idx: self._dispatch_event("change", self.GetSelected()))
        return self._tab_widget

    def Select(self, title: str):
        if title in self.tabs_map and self._tab_widget is not None:
            idx = list(self.tabs_map.keys()).index(title)
            self._tab_widget.setCurrentIndex(idx)
        return self

    def GetSelected(self) -> str:
        if self._tab_widget is not None:
            idx = self._tab_widget.currentIndex()
            keys = list(self.tabs_map.keys())
            if 0 <= idx < len(keys):
                return keys[idx]
        return ""

    def Remove(self, title: str):
        if title in self.tabs_map:
            idx = list(self.tabs_map.keys()).index(title)
            del self.tabs_map[title]
            if self._tab_widget is not None:
                self._tab_widget.removeTab(idx)
        return self

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        qss = f"""
        QTabWidget::pane {{
            border: 1px solid {palette['border']};
            background-color: {palette['surface']};
        }}
        QTabBar::tab {{
            background-color: {palette['surfaceSecondary']};
            color: {palette['foreground']};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {palette['surface']};
            border-bottom: 2px solid {palette['accent']};
        }}
        """
        self._widget.setStyleSheet(qss)


class NavigationView(GUIComponent):
    """Windows 11 Modern Sidebar Navigation View."""
    kind = "NavigationView"

    def __init__(self):
        super().__init__()
        self.nav_items: List[Tuple[str, GUIComponent, str]] = []
        self.active_title = ""
        self.btn_map: Dict[str, QPushButton] = {}
        self.content_area: Optional[QFrame] = None
        self.content_layout: Optional[QVBoxLayout] = None

    def Add(self, title: str, content: GUIComponent, icon: str = "home"):
        self.nav_items.append((title, content, icon))
        if not self.active_title:
            self.active_title = title
        return self

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        root = QWidget(parent)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame(root)
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(4)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Content Area
        self.content_area = QFrame(root)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(8, 8, 8, 8)

        layout.addWidget(sidebar)
        layout.addWidget(self.content_area, 1)

        self.btn_map = {}
        for title, content, icon_name in self.nav_items:
            glyph = Icon.ICON_MAP.get(icon_name.lower(), "📄")
            btn = QPushButton(f"  {glyph}  {title}", sidebar)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=title: self.Select(t))
            sidebar_layout.addWidget(btn)
            self.btn_map[title] = btn

        self._show_active_content()
        return root

    def Select(self, title: str):
        self.active_title = title
        self._show_active_content()
        self._dispatch_event("change", title)
        return self

    def GetSelected(self) -> str:
        return self.active_title

    def _show_active_content(self):
        if self.content_area is None or self.content_layout is None:
            return

        palette = _GLOBAL_THEME.get_palette()

        # Update button highlights
        for title, btn in self.btn_map.items():
            if title == self.active_title:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {palette['accent']};
                        color: {palette['accentText']};
                        border: none;
                        border-radius: 6px;
                        padding: 8px 12px;
                        text-align: left;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {palette['foreground']};
                        border: none;
                        border-radius: 6px;
                        padding: 8px 12px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {palette['surfaceTertiary']};
                    }}
                """)

        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # Show selected content
        for title, content, _ in self.nav_items:
            if title == self.active_title:
                content._reset_widget_tree()
                w = content._realize(self.content_area)
                self.content_layout.addWidget(w)
                break


class Table(GUIComponent):
    kind = "Table"

    def __init__(self, opts: Any = None):
        super().__init__()
        opts_dict = _normalize_dict(opts) if opts else {}
        self.columns = list(opts_dict.get("columns", ["Column 1"]))
        self.rows: List[List[Any]] = []
        self._table: Optional[QTableWidget] = None

    def AddRow(self, row: List[Any]):
        self.rows.append(list(row))
        if self._table is not None:
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)
            for col_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                self._table.setItem(row_idx, col_idx, item)
        return self

    def Clear(self):
        self.rows.clear()
        if self._table is not None:
            self._table.setRowCount(0)
        return self

    def RemoveRow(self, index: int):
        if 0 <= index < len(self.rows):
            del self.rows[index]
            if self._table is not None:
                self._table.removeRow(index)
        return self

    def GetRows(self) -> List[List[Any]]:
        return self.rows

    def OnSelect(self, callback: Any):
        return self._register_event("select", callback)

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        self._table = QTableWidget(len(self.rows), len(self.columns), parent)
        self._table.setHorizontalHeaderLabels(self.columns)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row_idx, row in enumerate(self.rows):
            for col_idx, val in enumerate(row):
                self._table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        return self._table

    def _on_selection_changed(self):
        if self._table is not None:
            selected_rows = self._table.selectionModel().selectedRows()
            if selected_rows:
                idx = selected_rows[0].row()
                if 0 <= idx < len(self.rows):
                    self._dispatch_event("select", self.rows[idx])

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        qss = f"""
        QTableWidget {{
            background-color: {palette['surface']};
            color: {palette['foreground']};
            border: 1px solid {palette['border']};
            gridline-color: {palette['border']};
            selection-background-color: {palette['accent']};
            selection-color: {palette['accentText']};
        }}
        QHeaderView::section {{
            background-color: {palette['surfaceSecondary']};
            color: {palette['foreground']};
            padding: 4px;
            border: 1px solid {palette['border']};
        }}
        """
        self._widget.setStyleSheet(qss)


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
        self._list_widget: Optional[QListWidget] = None

    def AddItem(self, item: str):
        self.items.append(str(item))
        if self._list_widget is not None:
            self._list_widget.addItem(str(item))
        return self

    def RemoveItem(self, item: str):
        if str(item) in self.items:
            idx = self.items.index(str(item))
            del self.items[idx]
            if self._list_widget is not None:
                item_obj = self._list_widget.takeItem(idx)
                del item_obj
        return self

    def Clear(self):
        self.items.clear()
        if self._list_widget is not None:
            self._list_widget.clear()
        return self

    def GetSelected(self) -> str:
        if self._list_widget is not None:
            cur = self._list_widget.currentItem()
            if cur is not None:
                return cur.text()
        return ""

    def OnSelect(self, callback: Any):
        return self._register_event("select", callback)

    def _build(self, parent: Optional[QWidget]) -> QWidget:
        self._list_widget = QListWidget(parent)
        for item in self.items:
            self._list_widget.addItem(item)
        self._list_widget.currentItemChanged.connect(
            lambda cur, prev: self._dispatch_event("select", cur.text() if cur else "")
        )
        return self._list_widget

    def _apply_style(self):
        super()._apply_style()
        if self._widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        qss = f"""
        QListWidget {{
            background-color: {palette['inputBg']};
            color: {palette['foreground']};
            border: 1px solid {palette['border']};
            selection-background-color: {palette['accent']};
            selection-color: {palette['accentText']};
        }}
        """
        self._widget.setStyleSheet(qss)


# ============================================================
# Menus & Toolbar
# ============================================================

class MenuBar:
    def __init__(self, root: Optional[QMainWindow] = None):
        self.root = root
        self._menubar: Optional[QMenuBar] = None

    def Add(self, title: str) -> "Menu":
        if self._menubar is None and self.root is not None:
            self._menubar = self.root.menuBar()
        sub_menu = QMenu(title, self._menubar)
        if self._menubar is not None:
            self._menubar.addMenu(sub_menu)
        return Menu(sub_menu)


class Menu:
    def __init__(self, qmenu: QMenu):
        self.qmenu = qmenu
        self._interpreter = None

    def Add(self, label: str, callback: Any):
        action = QAction(label, self.qmenu)

        def _cmd():
            if self._interpreter is not None:
                _invoke_callback(self._interpreter, callback, [])

        action.triggered.connect(_cmd)
        self.qmenu.addAction(action)
        return self

    def Separator(self):
        self.qmenu.addSeparator()
        return self


class ContextMenu(Menu):
    def __init__(self):
        super().__init__(QMenu())

    def _show_popup(self, global_pos):
        try:
            self.qmenu.exec(global_pos)
        except Exception:
            pass


class Toolbar(Container):
    kind = "Toolbar"
    _layout_type = "horizontal"

    def AddButton(self, text: str, callback: Any, icon: str = None):
        btn = Button({"text": text, "icon": icon, "variant": "subtle"})
        btn.OnClick(callback)
        self.Add(btn)
        return btn


# ============================================================
# Dialog Helpers
# ============================================================

def Alert(title: str, message: str):
    _get_or_create_qapp()
    QMessageBox.information(None, str(title), str(message))


def Confirm(title: str, message: str) -> bool:
    _get_or_create_qapp()
    ret = QMessageBox.question(
        None,
        str(title),
        str(message),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return ret == QMessageBox.StandardButton.Yes


def OpenFile(opts: Any = None) -> str:
    _get_or_create_qapp()
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Open File")
    file_path, _ = QFileDialog.getOpenFileName(None, title)
    return file_path or ""


def SaveFile(opts: Any = None) -> str:
    _get_or_create_qapp()
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Save File")
    file_path, _ = QFileDialog.getSaveFileName(None, title)
    return file_path or ""


def SelectFolder(opts: Any = None) -> str:
    _get_or_create_qapp()
    opts_dict = _normalize_dict(opts) if opts else {}
    title = opts_dict.get("title", "Select Folder")
    folder_path = QFileDialog.getExistingDirectory(None, title)
    return folder_path or ""


# ============================================================
# Window Class
# ============================================================

class Window:
    _ACTIVE_WINDOWS: List["Window"] = []

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
        self._window_widget: Optional[QMainWindow] = None
        self._central_widget: Optional[QWidget] = None
        self._central_layout: Optional[QVBoxLayout] = None
        self._running = False
        self._destroyed = False
        self._style: Dict[str, Any] = {}
        self._callbacks: Dict[str, Any] = {}
        self._interpreter = None

        Window._ACTIVE_WINDOWS.append(self)

    def _ensure_alive(self):
        if self._destroyed:
            raise _DestroyedError("Window")

    def SetTitle(self, title: str):
        self._ensure_alive()
        self.title = str(title)
        if self._window_widget is not None:
            self._window_widget.setWindowTitle(self.title)
        return self

    def GetTitle(self) -> str:
        return self.title

    def SetSize(self, width: int, height: int):
        self._ensure_alive()
        self.width = int(width)
        self.height = int(height)
        if self._window_widget is not None:
            self._window_widget.resize(self.width, self.height)
        return self

    def GetSize(self) -> Tuple[int, int]:
        if self._window_widget is not None:
            s = self._window_widget.size()
            return (s.width(), s.height())
        return (self.width, self.height)

    def SetMinimumSize(self, width: int, height: int):
        self.min_width = int(width)
        self.min_height = int(height)
        if self._window_widget is not None:
            self._window_widget.setMinimumSize(self.min_width, self.min_height)
        return self

    SetMinSize = SetMinimumSize

    def SetMaximumSize(self, width: int, height: int):
        self.max_width = int(width)
        self.max_height = int(height)
        if self._window_widget is not None:
            self._window_widget.setMaximumSize(self.max_width, self.max_height)
        return self

    SetMaxSize = SetMaximumSize

    def Center(self):
        if self._window_widget is not None:
            screen = self._window_widget.screen() or QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                x = (geom.width() - self.width) // 2 + geom.left()
                y = (geom.height() - self.height) // 2 + geom.top()
                self._window_widget.move(max(0, x), max(0, y))
        return self

    def Minimize(self):
        if self._window_widget is not None:
            self._window_widget.showMinimized()
        return self

    def Maximize(self):
        if self._window_widget is not None:
            self._window_widget.showMaximized()
        return self

    def Restore(self):
        if self._window_widget is not None:
            self._window_widget.showNormal()
        return self

    def SetResizable(self, resizable: bool):
        self.resizable_x = bool(resizable)
        self.resizable_y = bool(resizable)
        if self._window_widget is not None:
            if not self.resizable_x and not self.resizable_y:
                self._window_widget.setFixedSize(self.width, self.height)
            else:
                self._window_widget.setMinimumSize(0, 0)
                self._window_widget.setMaximumSize(16777215, 16777215)
        return self

    def Resizable(self, width: bool, height: bool):
        return self.SetResizable(width and height)

    def SetIcon(self, path: str):
        self.icon_path = str(path)
        if self._window_widget is not None and os.path.isfile(self.icon_path):
            self._window_widget.setWindowIcon(QIcon(self.icon_path))
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
        if self._window_widget is not None:
            self._apply_style()
        return self

    SetStyle = Style
    UseStyle = Style

    def _apply_style(self):
        if self._window_widget is None:
            return
        palette = _GLOBAL_THEME.get_palette()
        bg = self._style.get("background", self._style.get("bg", palette["background"]))
        self._window_widget.setStyleSheet(f"""
            QMainWindow {{
                background-color: {bg};
            }}
            QWidget#central {{
                background-color: {bg};
            }}
        """)
        try:
            hwnd = int(self._window_widget.winId())
            _set_window_dark_titlebar(hwnd, palette["mode"] == "dark")
        except Exception:
            pass

    def Add(self, *components: Any):
        self._ensure_alive()
        for comp in components:
            if isinstance(comp, (list, tuple)):
                self.Add(*comp)
                continue
            if isinstance(comp, MenuBar):
                comp.root = self._window_widget
                continue
            if not isinstance(comp, GUIComponent):
                raise BlazeTypeError(f"Window.Add expects GUI components, got {type(comp).__name__}")
            comp._window = self
            self.children.append(comp)
            if self._window_widget is not None and self._central_layout is not None:
                self._attach(comp)
        return self

    def _attach(self, component: GUIComponent):
        component._window = self
        w = component._realize(self._central_widget)
        if self._central_layout is not None:
            self._central_layout.addWidget(w)

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

    def _setup_window_widget(self, interpreter=None):
        _get_or_create_qapp()

        self._window_widget = QMainWindow()
        self._window_widget.setWindowTitle(self.title)

        # Apply sizing accurately
        self._window_widget.resize(self.width, self.height)

        if not self.resizable_x and not self.resizable_y:
            self._window_widget.setFixedSize(self.width, self.height)
        else:
            if self.min_width and self.min_height:
                self._window_widget.setMinimumSize(int(self.min_width), int(self.min_height))
            if self.max_width and self.max_height:
                self._window_widget.setMaximumSize(int(self.max_width), int(self.max_height))

        # Central widget and layout
        self._central_widget = QWidget(self._window_widget)
        self._central_widget.setObjectName("central")
        self._central_layout = QVBoxLayout(self._central_widget)
        self._central_layout.setContentsMargins(10, 10, 10, 10)
        self._central_layout.setSpacing(6)
        self._central_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._window_widget.setCentralWidget(self._central_widget)

        if self.centered:
            self.Center()

        icon = self.icon_path or _get_gui_icon_path()
        if icon and os.path.isfile(icon):
            self._window_widget.setWindowIcon(QIcon(icon))

        self._apply_style()

        # Connect window events
        class _WindowFilter(QObject):
            def __init__(self, win_obj: "Window"):
                super().__init__()
                self._win_obj = win_obj

            def eventFilter(self, watched, event):
                if event.type() == QEvent.Type.Close:
                    self._win_obj.Close()
                elif event.type() == QEvent.Type.Resize:
                    s = event.size()
                    self._win_obj._dispatch_window_event("resize", s.width(), s.height())
                elif event.type() == QEvent.Type.Move:
                    p = event.pos()
                    self._win_obj._dispatch_window_event("move", p.x(), p.y())
                elif event.type() == QEvent.Type.WindowStateChange:
                    if self._win_obj._window_widget.isMinimized():
                        self._win_obj._dispatch_window_event("minimize")
                    elif self._win_obj._window_widget.isMaximized():
                        self._win_obj._dispatch_window_event("maximize")
                return False

        self._window_filter = _WindowFilter(self)
        self._window_widget.installEventFilter(self._window_filter)

        self._bind_interpreter(self.children, interpreter)

        for component in self.children:
            self._attach(component)

    def Run(self, interpreter=None):
        self._ensure_alive()
        if self._running:
            raise BlazeRuntimeError("GUI window is already running", hint="Call app.Run() only once.")

        qapp = _get_or_create_qapp()

        if self._window_widget is None:
            self._setup_window_widget(interpreter)

        self._window_widget.show()
        self._running = True

        try:
            # If Qt event loop is not already running, run it
            if not getattr(qapp, "_blaze_loop_running", False):
                qapp._blaze_loop_running = True
                try:
                    qapp.exec()
                finally:
                    qapp._blaze_loop_running = False
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
        if self in Window._ACTIVE_WINDOWS:
            Window._ACTIVE_WINDOWS.remove(self)
        if self._window_widget is not None:
            try:
                self._window_widget.close()
                self._window_widget.deleteLater()
            finally:
                self._window_widget = None


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
