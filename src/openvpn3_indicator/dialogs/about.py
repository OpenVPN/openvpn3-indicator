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
from gi.repository import GLib, GObject, Gtk, Gio

from openvpn3_indicator.about import APPLICATION_NAME, APPLICATION_TITLE, APPLICATION_VERSION, APPLICATION_AUTHORS, APPLICATION_URL, APPLICATION_DESCRIPTION_SHORT


def construct_about_dialog():
    dialog = Gtk.AboutDialog()
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)

    dialog.set_program_name(APPLICATION_TITLE)
    dialog.set_logo_icon_name(APPLICATION_NAME)
    dialog.set_version(APPLICATION_VERSION)
    dialog.set_comments(APPLICATION_DESCRIPTION_SHORT)
    dialog.set_website(APPLICATION_URL)
    dialog.set_license_type(Gtk.License.AGPL_3_0)
    dialog.set_authors(APPLICATION_AUTHORS)
    dialog.show_all()
    return dialog
