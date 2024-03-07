#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.multi_notifier import MultiNotifier

class Test(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self,
            application_id='net.openvpn.openvpn3_indicator.test.multi_notifier',
            )
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)

    def on_activate(self, *args, **kwargs):
        pass
    def on_startup(self, *args, **kwargs):
        self.hold()
        self.multi_notifier = MultiNotifier(self, 'Test App')
        
        self.first_notifier = self.multi_notifier.new_notifier(
            identifier = 'startup',
            title = 'Test App',
            body = 'Started',
            icon = 'openvpn3-indicator',
            active = True,
            timespan = 10,
        )
        GLib.timeout_add(1000, self.on_schedule)
        GLib.timeout_add(5000, self.action_quit)
    
    def on_schedule(self, *args, **kwargs):
        self.multi_notifier.update()
        GLib.timeout_add(1000, self.on_schedule)

    def action_quit(self, *args, **kwargs):
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
