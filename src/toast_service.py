# MIT License
#
# Copyright (c) 2026 Fitrian Musya
#
# SPDX-License-Identifier: MIT

from gi.repository import Adw, Gtk


class ToastService:
    """Singleton service for showing toasts from anywhere in the app."""

    _instance = None
    _overlay = None

    @classmethod
    def get_default(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_overlay(self, overlay):
        """Set the ToastOverlay widget to use for displaying toasts."""
        self._overlay = overlay

    def show(self, message, timeout=2):
        """Show a toast with the given message."""
        if self._overlay is None:
            print(f"ToastService: no overlay set, message was: {message}")
            return
        toast = Adw.Toast(title=message, timeout=timeout)
        self._overlay.add_toast(toast)
