#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import *
from openvpn3_indicator.multi_indicator import MultiIndicator

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
        self.multi_indicator = MultiIndicator('Test App')

        self.first_indicator = self.multi_indicator.new_indicator()
        self.first_indicator.icon = 'openvpn3-indicator-idle'
        self.first_indicator.description = 'Test Description'
        self.first_indicator.title = 'Test Title'
        self.first_indicator.order_key = '1'
        menu = Gtk.Menu()
        menu_item = Gtk.MenuItem.new_with_label('Quit')
        menu_item.connect('activate', self.action_quit)
        menu.append(menu_item)
        menu.show_all()
        self.first_indicator.menu = menu
        self.first_indicator.active = True

        self.second_indicator = self.multi_indicator.new_indicator()
        self.second_indicator.icon = 'openvpn3-indicator-active'
        self.second_indicator.description = 'Test Description'
        self.second_indicator.title = 'Test Title'
        self.second_indicator.order_key = '2'
        self.second_indicator.menu = menu
        self.second_indicator.active=True
        
        GLib.timeout_add(1000, self.on_schedule)
        GLib.timeout_add(5000, self.action_quit)

    def on_schedule(self, *args, **kwargs):
        self.multi_indicator.update()
        GLib.timeout_add(1000, self.on_schedule)

    def action_quit(self, *args, **kwargs):
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
