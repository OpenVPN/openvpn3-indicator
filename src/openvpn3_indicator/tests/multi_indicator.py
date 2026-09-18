#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

# Manual test for MultiIndicator.
#
# Shows two test indicators, hides and re-shows one of them, runs a repair,
# re-creates them under fresh ids, and quits after TEST_DURATION seconds
# (default 60).  While it runs, restart
# the tray watcher and check that both icons come back and their menus work:
#
#   gnome-extensions disable appindicatorsupport@rgcjonas.gmail.com; sleep 3
#   gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
#
# or lock and unlock the screen.  Registration state can be inspected with:
#
#   busctl --user get-property org.kde.StatusNotifierWatcher /StatusNotifierWatcher \
#       org.kde.StatusNotifierWatcher RegisteredStatusNotifierItems

import logging
import os
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import *
from openvpn3_indicator.multi_indicator import MultiIndicator

TEST_DURATION = int(os.environ.get('TEST_DURATION', '60'))

class Test(Gtk.Application):
    def __init__(self):
        # Use a distinct application id: the real indicator treats a second
        # activation of its own id as a repair request.
        Gtk.Application.__init__(self,
            application_id=f'{APPLICATION_ID}.tests.multi_indicator',
            )
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)

    def on_activate(self, *args, **kwargs):
        pass

    def on_startup(self, *args, **kwargs):
        self.hold()
        self.multi_indicator = MultiIndicator('Test App')

        menu = Gtk.Menu()
        menu_item = Gtk.MenuItem.new_with_label('Quit')
        menu_item.connect('activate', self.action_quit)
        menu.append(menu_item)
        menu.show_all()

        self.first_indicator = self.multi_indicator.new_indicator()
        self.first_indicator.icon = 'openvpn3-indicator-idle'
        self.first_indicator.description = 'Test Description'
        self.first_indicator.title = 'Test Title'
        self.first_indicator.order_key = '1'
        self.first_indicator.menu = menu
        self.first_indicator.active = True

        self.second_indicator = self.multi_indicator.new_indicator()
        self.second_indicator.icon = 'openvpn3-indicator-active'
        self.second_indicator.description = 'Test Description'
        self.second_indicator.title = 'Test Title'
        self.second_indicator.order_key = '2'
        self.second_indicator.menu = menu
        self.second_indicator.active = True

        def at(fraction, callback):
            GLib.timeout_add(int(TEST_DURATION * 1000 * fraction), callback)

        GLib.timeout_add(1000, self.on_schedule)
        at(0.20, self.action_hide_second)
        at(0.35, self.action_repair)
        at(0.50, self.action_show_second)
        at(0.65, self.action_recreate)
        at(1.0, self.action_quit)

    def on_schedule(self, *args, **kwargs):
        self.multi_indicator.update()
        return GLib.SOURCE_CONTINUE

    def action_hide_second(self, *args, **kwargs):
        logging.info('Hiding second indicator')
        self.second_indicator.active = False
        return GLib.SOURCE_REMOVE

    def action_show_second(self, *args, **kwargs):
        logging.info('Showing second indicator again')
        self.second_indicator.active = True
        return GLib.SOURCE_REMOVE

    def action_repair(self, *args, **kwargs):
        logging.info('Running repair')
        self.multi_indicator.repair()
        return GLib.SOURCE_REMOVE

    def action_recreate(self, *args, **kwargs):
        logging.info('Recreating indicators with fresh ids')
        self.multi_indicator.recreate()
        return GLib.SOURCE_REMOVE

    def action_quit(self, *args, **kwargs):
        logging.info('Quitting')
        self.multi_indicator.close()
        self.release()
        return GLib.SOURCE_REMOVE

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    test = Test()
    test.run(sys.argv)
