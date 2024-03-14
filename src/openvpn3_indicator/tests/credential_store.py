#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import *
from openvpn3_indicator.credential_store import CredentialStore

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
        self.credential_store = CredentialStore()
        for config in self.credential_store.keys():
            credentials = self.credential_store[config]
            for key in credentials.keys():
                print(f'{config} {key} {"*"*len(credentials[key])}')

        print(self.credential_store['unknown']['unset'])
        self.credential_store['unknown']['unset'] = 'unpredicted'
        print(self.credential_store['unknown']['unset'])
        del self.credential_store['unknown']['unset']
        print(self.credential_store['unknown']['unset'])
        GLib.timeout_add(1000, self.on_schedule)
        GLib.timeout_add(5000, self.action_quit)

    def on_schedule(self, *args, **kwargs):
        GLib.timeout_add(1000, self.on_schedule)

    def action_quit(self, *args, **kwargs):
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
