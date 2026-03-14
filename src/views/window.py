# MIT License
#
# Copyright (c) 2026 Fitrian Musya
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# SPDX-License-Identifier: MIT

import os
from gi.repository import Adw, Gio, GLib, GObject, Gtk

from ..backend import load_data, Save_As
from .welcome import GriffinWelcomePage
from ..services.toast_service import ToastService


class DataRow(GObject.Object):
    """A GObject wrapper for a single row of data from a DataFrame."""

    def __init__(self, values: list[str]):
        super().__init__()
        self._values = values

    def get_value(self, col_index: int) -> str:
        if 0 <= col_index < len(self._values):
            return self._values[col_index]
        return ""


@Gtk.Template(resource_path="/org/griffin/app/window.ui")
class GriffinWindow(Adw.ApplicationWindow):
    __gtype_name__ = "GriffinWindow"

    status_label = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()
    data_scroll = Gtk.Template.Child()
    stack1 = Gtk.Template.Child()
    stack2 = Gtk.Template.Child()
    stack3 = Gtk.Template.Child()
    save_as_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        ToastService.get_default().set_overlay(self.toast_overlay)

        self.filepaths = ""
        # Register window actions for toolbar buttons
        self._create_action("open-file", self.on_open_file)
        self._create_action("to-excel", self.save_to_excel)
        self._create_action("to-json", self.save_to_json)
        self._create_action("import-file", self.on_import_file)

        # Show welcome page on first run
        settings = Gio.Settings.new("org.griffin.app")
        if settings.get_boolean("first-run"):
            welcome = GriffinWelcomePage(transient_for=self)
            welcome.connect("close-request", self._on_welcome_closed)
            welcome.present()

    def _on_welcome_closed(self, welcome):
        ToastService.get_default().show("Welcome to Griffin! Let's get started.")
        return False

    def _create_action(self, name, callback):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def on_open_file(self, action, param):
        dialog = Gtk.FileDialog()

        # csv filter
        csv_filter = Gtk.FileFilter()
        csv_filter.set_name("CSV files")
        csv_filter.add_pattern("*.csv")

        # list store for filter
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(csv_filter)

        dialog.set_filters(filters)
        dialog.open(self, None, self.on_file_selected)

    def on_file_selected(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            filepath = file.get_path()
            self.filepaths = filepath
            df = load_data(filepath)
            self._build_table(df)

            filename = os.path.basename(filepath)
            row_count, col_count = df.shape
            self.status_label.set_text(
                f"{filename}  —  {row_count} rows × {col_count} columns"
            )
            ToastService.get_default().show(f"Loaded {filename}")
            self.save_as_button.set_sensitive(True)
        except GLib.Error:
            print("File selection cancelled")

    def _build_table(self, df):
        """Build a Gtk.ColumnView from a pandas DataFrame and display it."""
        # Remove previous table if any
        existing = self.data_scroll.get_child()
        if existing:
            self.data_scroll.set_child(None)

        columns = list(df.columns)

        # Create list store and populate with DataRow objects
        store = Gio.ListStore.new(DataRow)
        for _, row in df.iterrows():
            values = [str(v) for v in row.values]
            store.append(DataRow(values))

        # Create selection model
        selection = Gtk.SingleSelection(model=store)

        # Create ColumnView
        column_view = Gtk.ColumnView(model=selection)
        column_view.set_show_row_separators(True)
        column_view.set_show_column_separators(True)
        column_view.add_css_class("data-table")

        # Add a column for each DataFrame column
        for col_index, col_name in enumerate(columns):
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", self._on_factory_setup)
            factory.connect("bind", self._on_factory_bind, col_index)

            column = Gtk.ColumnViewColumn(title=col_name, factory=factory)
            column.set_resizable(True)
            column.set_expand(True)
            column_view.append_column(column)

        self.data_scroll.set_child(column_view)

    def _on_factory_setup(self, factory, list_item):
        label = Gtk.Label(xalign=0)
        label.set_margin_start(6)
        label.set_margin_end(6)
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        label.set_ellipsize(3)
        list_item.set_child(label)

    def _on_factory_bind(self, factory, list_item, col_index):
        label = list_item.get_child()
        data_row = list_item.get_item()
        label.set_text(data_row.get_value(col_index))

    def save_to_excel(self, action, param):
        if not self.filepaths:
            ToastService.get_default().show("No file loaded to save.")
            return

        dialog = Gtk.FileDialog()
        dialog.set_initial_name("data.xlsx")

        xlsx_filter = Gtk.FileFilter()
        xlsx_filter.set_name("Excel files (*.xlsx)")
        xlsx_filter.add_pattern("*.xlsx")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(xlsx_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(xlsx_filter)

        dialog.save(self, None, self._on_save_excel_finish)

    def _on_save_excel_finish(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            dest_path = file.get_path()
            if not dest_path.endswith(".xlsx"):
                dest_path += ".xlsx"
            sv = Save_As()
            sv.to_excel(self.filepaths, dest_path)
            ToastService.get_default().show(f"Saved as {os.path.basename(dest_path)}")
        except GLib.Error:
            print("Save (Excel) cancelled")

    def save_to_json(self, action, param):
        if not self.filepaths:
            ToastService.get_default().show("No file loaded to save.")
            return

        dialog = Gtk.FileDialog()
        dialog.set_initial_name("data.json")

        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON files (*.json)")
        json_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(json_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(json_filter)

        dialog.save(self, None, self._on_save_json_finish)

    def _on_save_json_finish(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            dest_path = file.get_path()
            if not dest_path.endswith(".json"):
                dest_path += ".json"
            sv = Save_As()
            sv.to_json(self.filepaths, dest_path)
            ToastService.get_default().show(f"Saved as {os.path.basename(dest_path)}")
        except GLib.Error:
            print("Save (JSON) cancelled")

    def on_import_file(self, action, param):
        print("Import file")
