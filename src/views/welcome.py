# MIT License
#
# Copyright (c) 2026 Fitrian Musya
#
# SPDX-License-Identifier: MIT

from gi.repository import Adw, Gio, Gtk  # type: ignore


@Gtk.Template(resource_path="/org/griffin/app/welcome.ui")
class GriffinWelcomePage(Adw.Window):
    __gtype_name__ = "GriffinWelcomePage"

    get_started_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @Gtk.Template.Callback()
    def on_get_started_clicked(self, button):
        settings = Gio.Settings.new("org.griffin.app")
        settings.set_boolean("first-run", False)
        self.close()
