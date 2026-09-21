"""
Comprehensive regression test suite for BlazeLang PySide6 GUI module.
"""
import unittest
import sys
from blazelang.stdlib.Gui import (
    create_gui_module, _GLOBAL_THEME, ThemeSystem, Window, Label, Text,
    Button, Input, PasswordInput, Checkbox, Toggle, Radio, ComboBox,
    Slider, ProgressBar, TextArea, Image, VideoWidget, Container,
    Panel, Column, Row, Stack, Card, Grid, ScrollView, SplitView,
    Spacer, Divider, Tabs, NavigationView, Table, List,
    MenuBar, Menu, ContextMenu, Toolbar,
    Alert, Confirm, OpenFile, SaveFile, SelectFolder
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QLineEdit,
    QCheckBox, QRadioButton, QComboBox, QSlider, QProgressBar,
    QTextEdit, QScrollArea, QSplitter, QTabWidget, QTableWidget,
    QListWidget, QFrame
)


class DummyInterpreter:
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)


class TestGUI20PySide6Regression(unittest.TestCase):

    def setUp(self):
        self.interpreter = DummyInterpreter()
        self.gui = create_gui_module(self.interpreter)

    def test_no_tkinter_dependency(self):
        self.assertNotIn("tkinter", sys.modules)

    def test_window_sizing_and_geometry(self):
        # Explicit width and height
        app = self.gui["Create"]("Geometry Test", 750, 520)
        self.assertEqual(app.width, 750)
        self.assertEqual(app.height, 520)

        app._setup_window_widget(self.interpreter)
        self.assertEqual(app.GetSize(), (750, 520))

        # Dynamic resizing
        app.SetSize(820, 610)
        self.assertEqual(app.GetSize(), (820, 610))

        # Title
        app.SetTitle("Updated Title")
        self.assertEqual(app.GetTitle(), "Updated Title")
        self.assertEqual(app._window_widget.windowTitle(), "Updated Title")

        app.Close()
        self.assertTrue(app._destroyed)

    def test_multi_window_management(self):
        win1 = self.gui["Create"]("Win 1", 400, 300)
        win2 = self.gui["Create"]("Win 2", 500, 350)
        win1._setup_window_widget(self.interpreter)
        win2._setup_window_widget(self.interpreter)

        self.assertEqual(win1.GetSize(), (400, 300))
        self.assertEqual(win2.GetSize(), (500, 350))

        win1.Close()
        self.assertTrue(win1._destroyed)
        self.assertFalse(win2._destroyed)

        win2.Close()
        self.assertTrue(win2._destroyed)

    def test_widget_realization_and_events(self):
        app = self.gui["Create"]("Events Test", 600, 400)

        # Button
        btn = self.gui["Button"]({"text": "Submit", "variant": "primary", "icon": "check"})
        clicks = []
        btn.OnClick(lambda: clicks.append("clicked"))

        # Input
        inp = self.gui["Input"]({"value": "Initial", "placeholder": "Type here"})
        changes = []
        inp.OnChange(lambda val: changes.append(val))

        # Checkbox
        chk = self.gui["Checkbox"]({"text": "Agree", "checked": False})
        toggles = []
        chk.OnChange(lambda val: toggles.append(val))

        # Radio
        r1 = self.gui["Radio"]("Opt 1", "grp", "1")
        r2 = self.gui["Radio"]("Opt 2", "grp", "2")
        r1.SetChecked(True)

        # ComboBox
        combo = self.gui["ComboBox"](["Red", "Green", "Blue"])

        # Slider & Progress
        slider = self.gui["Slider"]({"min": 0, "max": 100, "value": 25})
        progress = self.gui["ProgressBar"](25)

        # TextArea
        txt = self.gui["TextArea"]("Start text")

        app.Add(btn, inp, chk, r1, r2, combo, slider, progress, txt)
        app._setup_window_widget(self.interpreter)

        # Verify underlying Qt classes
        self.assertIsInstance(btn._widget, QPushButton)
        self.assertIsInstance(inp._widget, QLineEdit)
        self.assertIsInstance(chk._widget, QCheckBox)
        self.assertIsInstance(r1._widget, QRadioButton)
        self.assertIsInstance(r2._widget, QRadioButton)
        self.assertIsInstance(combo._widget, QComboBox)
        self.assertIsInstance(slider._widget, QSlider)
        self.assertIsInstance(progress._widget, QProgressBar)
        self.assertIsInstance(txt._widget, QTextEdit)

        # Trigger events
        btn._widget.click()
        self.assertEqual(clicks, ["clicked"])

        # Value updates
        inp.SetValue("New Input")
        self.assertEqual(inp.GetValue(), "New Input")

        chk.SetChecked(True)
        self.assertTrue(chk.IsChecked())

        r2.SetChecked(True)
        self.assertEqual(r2.GetValue(), "2")

        combo.SetValue("Green")
        self.assertEqual(combo.GetValue(), "Green")

        slider.SetValue(80)
        self.assertEqual(slider.GetValue(), 80.0)

        progress.SetValue(80)
        self.assertEqual(progress.value, 80.0)

        txt.SetValue("Multiline\nUpdated")
        self.assertEqual(txt.GetValue(), "Multiline\nUpdated")

        app.Close()

    def test_containers_and_navigation(self):
        app = self.gui["Create"]("Layouts Test", 700, 500)

        card = self.gui["Card"]({"padding": 10})
        col = self.gui["Column"]()
        row = self.gui["Row"]()
        grid = self.gui["Grid"]({"columns": 3, "rows": 3})
        scroll = self.gui["ScrollView"]()
        split = self.gui["SplitView"]({"orientation": "horizontal", "ratio": 0.4})
        spacer = self.gui["Spacer"](16)
        divider = self.gui["Divider"]("horizontal")
        tabs = self.gui["Tabs"]()
        nav = self.gui["NavigationView"]()
        table = self.gui["Table"]({"columns": ["Col A", "Col B"]})
        lst = self.gui["List"](["A", "B", "C"])

        table.AddRow(["Val 1", "Val 2"])
        table.AddRow(["Val 3", "Val 4"])
        self.assertEqual(len(table.GetRows()), 2)
        table.RemoveRow(0)
        self.assertEqual(len(table.GetRows()), 1)

        lst.AddItem("D")
        self.assertIn("D", lst.items)
        lst.RemoveItem("D")
        self.assertNotIn("D", lst.items)

        t1 = tabs.Add("Tab 1")
        t1.Add(self.gui["Label"]("Tab 1 content"))

        page = self.gui["Container"]()
        page.Add(self.gui["Label"]("Page Content"))
        nav.Add("Home", page, "home")
        self.assertEqual(nav.GetSelected(), "Home")

        app.Add(card, col, row, grid, scroll, spacer, divider)
        app._setup_window_widget(self.interpreter)

        self.assertIsInstance(card._widget, QFrame)
        self.assertIsInstance(scroll._widget, QScrollArea)

        app.Close()

    def test_theme_system(self):
        self.gui["SetTheme"]("dark")
        self.assertEqual(_GLOBAL_THEME.mode, "dark")
        palette = _GLOBAL_THEME.get_palette()
        self.assertEqual(palette["mode"], "dark")

        self.gui["SetTheme"]("light")
        self.assertEqual(_GLOBAL_THEME.mode, "light")
        palette = _GLOBAL_THEME.get_palette()
        self.assertEqual(palette["mode"], "light")


if __name__ == "__main__":
    unittest.main()
