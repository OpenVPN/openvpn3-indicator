#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import APPLICATION_ID
from openvpn3_indicator.dialogs.credentials import construct_credentials_dialog, CredentialsUserInput

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

        user_inputs = [
                CredentialsUserInput(name='Username', mask=False, value='user', can_store=True),
                CredentialsUserInput(name='Password', mask=True, value=None, can_store=True),
                CredentialsUserInput(name='Other', mask=True, value='rehto', can_store=True),
                ]
        
        dialog = construct_credentials_dialog('Test', user_inputs, on_connect=self.action_connect, on_cancel=self.action_quit)
        dialog.set_visible(True)

        GLib.timeout_add(1000, self.on_schedule)
        GLib.timeout_add(60000, self.action_quit)

    def on_schedule(self, *args, **kwargs):
        GLib.timeout_add(1000, self.on_schedule)

    def action_connect(self, user_inputs, store):
        print(f'Result: {dict([(ui.name, ui.value) for ui in user_inputs])}, Store: {store}')
        self.action_quit()

    def action_quit(self, *args, **kwargs):
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
