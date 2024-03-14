#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import APPLICATION_ID
from openvpn3_indicator.dialogs.configuration import construct_configuration_select_dialog

class Test(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self,
            application_id=APPLICATION_ID,
            )
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)

    def on_activate(self, *args, **kwargs):
        pass
    def on_startup(self, *args, **kwargs):
        self.hold()

        dialog = construct_configuration_select_dialog(on_import=self.action_import, on_cancel=self.action_quit)
        dialog.set_visible(True)

        GLib.timeout_add(1000, self.on_schedule)
        GLib.timeout_add(60000, self.action_quit)

    def on_schedule(self, *args, **kwargs):
        GLib.timeout_add(1000, self.on_schedule)

    def action_import(self, *args, **kwargs):
        print(f'Result: {args} {kwargs}')
        self.action_quit()

    def action_quit(self, *args, **kwargs):
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
