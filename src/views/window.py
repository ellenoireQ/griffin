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
    stack = Gtk.Template.Child()
    save_as_button = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    sidebar = Gtk.Template.Child()
    sidebar_separator = Gtk.Template.Child()
    _search_some = Gtk.Template.Child()
    _set_range = Gtk.Template.Child()
    _view_some = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        ToastService.get_default().set_overlay(self.toast_overlay)

        self.filepaths = ""
        self.current_df = None
        self.current_filename = ""
        self.total_rows = 0
        self.row_limit = None
        self.train_start_range = ""
        self.train_end_range = ""
        self._row_limit_dialog = None
        self._row_limit_spin = None
        self._set_range_dialog = None
        self._set_range_start_entry = None
        self._set_range_end_entry = None

        # Register window actions for toolbar buttons
        self._create_action("open-file", self.on_open_file)
        self._create_action("to-excel", self.save_to_excel)
        self._create_action("to-json", self.save_to_json)
        self._create_action("import-file", self.on_import_file)
        self._create_action("show-analytics", self.show_analytics_page)
        self._create_action("show-plot", self.show_plot_page)
        self._create_action("show-train", self.show_train_page)
        self._create_action("toggle-search", self.toggle_search)
        self._create_action("toggle-set-range", self.toggle_set_range)
        self._create_action("toggle-expand-data", self.toggle_expand_data)

        self.search_entry.connect("search-changed", self.on_search_changed)
        self.stack.connect("notify::visible-child-name", self._on_stack_page_changed)
        self._set_data_actions_enabled(False)
        self._update_page_toolbar_state(self.stack.get_visible_child_name() or "analytics")

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
            self.current_filename = os.path.basename(filepath)
            self._load_current_file()
            ToastService.get_default().show(f"Loaded {self.current_filename}")
        except GLib.Error:
            print("File selection cancelled")
        except Exception as err:
            self._reset_loaded_data()
            ToastService.get_default().show(f"Failed to load CSV: {err}")

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

    def _filter_dataframe(self, query):
        if self.current_df is None:
            return None

        text = query.strip()
        if not text:
            return self.current_df

        lowered = text.casefold()
        mask = self.current_df.astype(str).apply(
            lambda column: column.str.casefold().str.contains(lowered, na=False)
        )
        return self.current_df[mask.any(axis=1)]

    def _update_status_label(self, visible_rows=None):
        if self.current_df is None:
            self.status_label.set_text("No data loaded. Open a CSV file to get started.")
            return

        loaded_rows, col_count = self.current_df.shape
        total_rows = self.total_rows or loaded_rows

        if self.row_limit is None and (visible_rows is None or visible_rows == loaded_rows):
            self.status_label.set_text(
                f"{self.current_filename}  —  {total_rows} rows × {col_count} columns"
            )
            return

        if visible_rows is None:
            visible_rows = loaded_rows

        self.status_label.set_text(
            f"{self.current_filename}  —  showing {visible_rows} of {total_rows} rows × {col_count} columns"
        )

    def _set_data_actions_enabled(self, enabled):
        self.save_as_button.set_sensitive(enabled)
        self._search_some.set_sensitive(enabled)
        self._view_some.set_sensitive(enabled)
        self.search_entry.set_sensitive(enabled)

        if not enabled:
            self.search_entry.set_text("")
            self.search_entry.set_visible(False)

    def _update_page_toolbar_state(self, page_name):
        is_train_page = page_name == "train"

        self._set_range.set_sensitive(is_train_page)

        if page_name != "analytics":
            self.search_entry.set_visible(False)

    def _on_stack_page_changed(self, stack, _param_spec):
        self._update_page_toolbar_state(stack.get_visible_child_name() or "analytics")

    def _reset_loaded_data(self):
        self.filepaths = ""
        self.current_df = None
        self.current_filename = ""
        self.total_rows = 0
        self.row_limit = None
        self.data_scroll.set_child(None)
        self._set_data_actions_enabled(False)
        self._update_status_label()

    def _load_current_file(self):
        if not self.filepaths:
            return

        df = load_data(self.filepaths, self.row_limit)
        self.current_df = df
        self.total_rows = self._count_total_rows(self.filepaths)
        self.search_entry.set_text("")
        self._build_table(df)
        self._update_status_label(df.shape[0])
        self.save_as_button.set_sensitive(True)
        self._set_data_actions_enabled(True)

    def _count_total_rows(self, filepath):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as csv_file:
            line_count = sum(1 for _ in csv_file)
        return max(0, line_count - 1)

    def _create_row_limit_dialog(self):
        dialog = Gtk.Dialog(title="Expand Data", transient_for=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Apply", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        label = Gtk.Label(
            label="Set the maximum number of rows to load from the CSV file:",
            xalign=0,
        )
        spin = Gtk.SpinButton.new_with_range(1, 1000000, 1)
        spin.set_hexpand(True)
        spin.set_value(float(self.row_limit or max(1, min(self.total_rows, 100))))

        content.append(label)
        content.append(spin)

        dialog.connect("response", self._on_row_limit_dialog_response)
        self._row_limit_dialog = dialog
        self._row_limit_spin = spin

    def _create_set_range_dialog(self):
        dialog = Gtk.Dialog(title="Set Range", transient_for=self, modal=True)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Apply", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        label = Gtk.Label(
            label="Set the start and end range for training:",
            xalign=0,
        )
        start_entry = Gtk.Entry()
        start_entry.set_placeholder_text("Start range")
        start_entry.set_hexpand(True)
        start_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        start_entry.set_activates_default(False)

        end_entry = Gtk.Entry()
        end_entry.set_placeholder_text("End range")
        end_entry.set_hexpand(True)
        end_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)
        end_entry.set_activates_default(False)

        content.append(label)
        content.append(start_entry)
        content.append(end_entry)

        dialog.connect("response", self._on_set_range_dialog_response)
        self._set_range_dialog = dialog
        self._set_range_start_entry = start_entry
        self._set_range_end_entry = end_entry

    def _focus_set_range_start_entry(self):
        if self._set_range_start_entry is not None:
            self._set_range_start_entry.grab_focus()
        return False

    def _on_row_limit_dialog_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK and self.filepaths:
            new_limit = int(self._row_limit_spin.get_value())
            self.row_limit = new_limit
            try:
                self._load_current_file()
                ToastService.get_default().show(
                    f"Loaded {min(self.total_rows, new_limit)} rows from {self.current_filename}"
                )
            except Exception as err:
                ToastService.get_default().show(f"Failed to reload CSV: {err}")

        dialog.hide()

    def _on_set_range_dialog_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            self.train_start_range = self._set_range_start_entry.get_text().strip()
            self.train_end_range = self._set_range_end_entry.get_text().strip()

            if self.train_start_range or self.train_end_range:
                ToastService.get_default().show(
                    f"Range set: {self.train_start_range or '-'} → {self.train_end_range or '-'}"
                )

        dialog.hide()

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

    def toggle_search(self, action, param):
        if self.current_df is None:
            return

        is_visible = self.search_entry.get_visible()
        self.search_entry.set_visible(not is_visible)
        self.stack.set_visible_child_name("analytics")

        if is_visible:
            self.search_entry.set_text("")
            self._build_table(self.current_df)
            self._update_status_label()
            return

        self.search_entry.grab_focus()

    def toggle_set_range(self, action, param):
        if self.stack.get_visible_child_name() != "train":
            return

        if self._set_range_dialog is None:
            self._create_set_range_dialog()

        self._set_range_start_entry.set_text(self.train_start_range)
        self._set_range_end_entry.set_text(self.train_end_range)
        self._set_range_dialog.present()

        GLib.idle_add(self._focus_set_range_start_entry)

    def on_search_changed(self, entry):
        filtered_df = self._filter_dataframe(entry.get_text())
        if filtered_df is None:
            return

        self.stack.set_visible_child_name("analytics")
        self._build_table(filtered_df)
        self._update_status_label(filtered_df.shape[0])

    def toggle_expand_data(self, action, param):
        if self.current_df is None:
            return

        self.stack.set_visible_child_name("analytics")
        if self._row_limit_dialog is None:
            self._create_row_limit_dialog()

        self._row_limit_spin.set_range(1, max(1, self.total_rows or 1))
        self._row_limit_spin.set_value(float(self.row_limit or max(1, min(self.total_rows, 100))))
        self._row_limit_dialog.present()

    def show_analytics_page(self, action, param):
        self.stack.set_visible_child_name("analytics")
        self._update_page_toolbar_state("analytics")

    def show_plot_page(self, action, param):
        self.stack.set_visible_child_name("plot")
        self._update_page_toolbar_state("plot")

    def show_train_page(self, action, param):
        self.stack.set_visible_child_name("train")
        self._update_page_toolbar_state("train")
