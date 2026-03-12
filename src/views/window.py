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

from gi.repository import Adw, Gio, Gtk  # type: ignore
from .welcome import GriffinWelcomePage
from ..services.toast_service import ToastService


@Gtk.Template(resource_path="/org/griffin/app/window.ui")
class GriffinWindow(Adw.ApplicationWindow):
    __gtype_name__ = "GriffinWindow"

    label1 = Gtk.Template.Child()
    button = Gtk.Template.Child()
    toast_overlay = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        ToastService.get_default().set_overlay(self.toast_overlay)

        # Register window actions for toolbar buttons
        self._create_action("new-file", self.on_new_file)
        self._create_action("open-file", self.on_open_file)
        self._create_action("save-file", self.on_save_file)
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

    def on_new_file(self, action, param):
        print("New file")

    def on_open_file(self, action, param):
        print("Open file")

    def on_save_file(self, action, param):
        print("Save file")

    def on_import_file(self, action, param):
        print("Import file")

    @Gtk.Template.Callback()
    def ok_button_clicked(self, button):
        ToastService.get_default().show("Ok button clicked!")
