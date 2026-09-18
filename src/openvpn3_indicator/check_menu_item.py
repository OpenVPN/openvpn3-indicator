#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

#
# openvpn3-indicator - Simple indicator application for OpenVPN3.
# Copyright (C) 2024 Grzegorz Gutowski <grzegorz.gutowski@uj.edu.pl>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License,
# or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.
# If not, see <https://www.gnu.org/licenses/>.
#

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

###
#
# StateCheckMenuItem
#
###

class StateCheckMenuItem(Gtk.CheckMenuItem):
    """A check menu item whose mark only reflects program state.

    The menus of this application are never shown by GTK itself.  They are
    exported over D-Bus by libdbusmenu and rendered by the status host, which
    draws a checked item's mark in the menu's left border.  The host also
    activates items on our side: it calls gtk_menu_item_activate() for every
    click, and libdbusmenu does the same for an item with a submenu whenever
    that submenu is about to be shown.  A plain GtkCheckMenuItem toggles on
    activation, so the mark of a connected session would flip every time its
    submenu is opened.

    This item ignores the toggle on activation (the 'activate' signal is still
    emitted, so handlers connected to it keep working) and changes its mark
    only through set_state().
    """

    def __init__(self, label, active=False):
        super().__init__(label=label)
        self._changing_state = False
        self.set_state(active)

    def set_state(self, active):
        self._changing_state = True
        try:
            self.set_active(bool(active))
        finally:
            self._changing_state = False

    def do_activate(self):
        # GtkCheckMenuItem performs its toggle in the class handler of the
        # 'activate' signal; chain up only for our own state changes.
        if self._changing_state:
            Gtk.CheckMenuItem.do_activate(self)
