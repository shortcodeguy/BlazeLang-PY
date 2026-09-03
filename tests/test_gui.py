"""
Unit tests for BlazeLang GUI 2.0 Module
"""

import unittest
from blazelang.stdlib.Gui import create_gui_module, _GLOBAL_THEME


class DummyInterpreter:
    pass


class TestGUI20Module(unittest.TestCase):

    def setUp(self):
        self.interpreter = DummyInterpreter()
        self.gui = create_gui_module(self.interpreter)

    def test_gui_create_overloads(self):
        # Traditional Create
        app1 = self.gui["Create"]("Test App", 600, 400)
        self.assertEqual(app1.title, "Test App")
        self.assertEqual(app1.width, 600)
        self.assertEqual(app1.height, 400)

        # Object Create
        app2 = self.gui["Create"]({
            "title": "Modern App",
            "width": 900,
            "height": 600,
            "theme": "dark",
            "centered": True,
            "resizable": False,
        })
        self.assertEqual(app2.title, "Modern App")
        self.assertEqual(app2.width, 900)
        self.assertEqual(app2.height, 600)
        self.assertEqual(_GLOBAL_THEME.mode, "dark")

    def test_theme_system(self):
        self.gui["SetTheme"]("light")
        self.assertEqual(_GLOBAL_THEME.mode, "light")

        self.gui["SetTheme"]({"mode": "dark", "accent": "#0078D4"})
        self.assertEqual(_GLOBAL_THEME.mode, "dark")
        palette = _GLOBAL_THEME.get_palette()
        self.assertEqual(palette["accent"], "#0078D4")

    def test_text_and_label_api(self):
        label = self.gui["Label"]("Hello World")
        self.assertEqual(label.GetText(), "Hello World")
        label.SetText("New Label")
        self.assertEqual(label.GetText(), "New Label")

        text = self.gui["Text"]("BlazeLang", {"size": 24, "weight": "bold", "alignment": "center"})
        self.assertEqual(text.GetText(), "BlazeLang")
        text.SetFontSize(18)
        self.assertEqual(text.GetStyle("fontSize"), 18)

    def test_button_variants_and_methods(self):
        btn = self.gui["Button"]({"text": "Save", "icon": "save", "variant": "primary"})
        self.assertEqual(btn.text, "Save")
        self.assertEqual(btn.icon, "save")
        self.assertEqual(btn.variant, "primary")

        btn.SetText("Updated Save")
        self.assertEqual(btn.text, "Updated Save")
        btn.SetEnabled(False)
        self.assertFalse(btn._enabled)

    def test_input_and_password_input(self):
        inp = self.gui["Input"]({"value": "Rohit", "placeholder": "Enter name"})
        self.assertEqual(inp.GetValue(), "Rohit")
        inp.SetValue("Alex")
        self.assertEqual(inp.GetValue(), "Alex")

        pwd = self.gui["PasswordInput"]("Password")
        pwd.SetValue("secret123")
        self.assertEqual(pwd.GetValue(), "secret123")

    def test_checkbox_toggle_radio(self):
        chk = self.gui["Checkbox"]("Remember me")
        self.assertFalse(chk.IsChecked())
        chk.SetChecked(True)
        self.assertTrue(chk.IsChecked())

        tog = self.gui["Toggle"]("Enable feature")
        self.assertFalse(tog.IsChecked())
        tog.SetChecked(True)
        self.assertTrue(tog.IsChecked())

        r1 = self.gui["Radio"]("Option 1", "grp", "1")
        r2 = self.gui["Radio"]("Option 2", "grp", "2")
        r1.SetChecked(True)
        self.assertTrue(r1.IsChecked())
        self.assertEqual(r2.GetValue(), "1")

    def test_combobox_slider_progress_textarea(self):
        combo = self.gui["ComboBox"](["India", "USA", "UK"])
        self.assertEqual(combo.GetValue(), "India")
        combo.AddItem("Japan")
        self.assertIn("Japan", combo.items)

        slider = self.gui["Slider"]({"min": 0, "max": 100, "value": 50})
        self.assertEqual(slider.GetValue(), 50.0)
        slider.SetValue(75)
        self.assertEqual(slider.GetValue(), 75.0)

        prog = self.gui["ProgressBar"](40)
        self.assertEqual(prog.value, 40)

        area = self.gui["TextArea"]("Type here...")
        area.SetValue("Hello BlazeLang")
        self.assertEqual(area.GetValue(), "Hello BlazeLang")

    def test_containers_and_card_layouts(self):
        col = self.gui["Column"]()
        row = self.gui["Row"]()
        card = self.gui["Card"]({"padding": 20})
        grid = self.gui["Grid"]({"columns": 4, "rows": 4})

        lbl = self.gui["Label"]("Inside Card")
        card.Add(lbl)
        self.assertIn(lbl, card.children)

        col.Add(card, row)
        self.assertEqual(len(col.children), 2)

        btn = self.gui["Button"]("Grid Btn")
        grid.Add(btn, 0, 1)
        self.assertIn(btn, grid.children)
        self.assertEqual(grid.grid_positions[btn], (0, 1, 1, 1))

    def test_navigation_view_and_tabs(self):
        tabs = self.gui["Tabs"]()
        home = tabs.Add("Home")
        settings = tabs.Add("Settings")
        home.Add(self.gui["Label"]("Home Page"))
        settings.Add(self.gui["Label"]("Settings Page"))
        self.assertIn("Home", tabs.tabs_map)
        self.assertIn("Settings", tabs.tabs_map)

        nav = self.gui["NavigationView"]()
        page1 = self.gui["Container"]()
        nav.Add("Dashboard", page1, "home")
        self.assertEqual(nav.GetSelected(), "Dashboard")

    def test_table_and_list(self):
        table = self.gui["Table"]({"columns": ["Name", "Age"]})
        table.AddRow(["Rohit", 13])
        table.AddRow(["Alex", 14])
        self.assertEqual(len(table.GetRows()), 2)
        table.RemoveRow(0)
        self.assertEqual(len(table.GetRows()), 1)

        lst = self.gui["List"](["Item 1", "Item 2"])
        lst.AddItem("Item 3")
        self.assertIn("Item 3", lst.items)
        lst.RemoveItem("Item 3")
        self.assertNotIn("Item 3", lst.items)


if __name__ == "__main__":
    unittest.main()
