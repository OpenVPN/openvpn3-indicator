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


def construct_appindicator_missing_dialog():
    dialog = Gtk.MessageDialog()
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
    dialog.set_markup('<b>AppIndicator not available</b>')
    dialog.format_secondary_text('OpenVPN Indicator requires AppIndicator to run. Please install AppIndicator plugin for your desktop.')

    def on_dialog_response(_object, response):
        dialog.destroy()

    dialog.connect('response', on_dialog_response)
    dialog.show_all()
    return dialog


def construct_dbus_missing_dialog():
    dialog = Gtk.MessageDialog()
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
    dialog.set_markup('<b>D-Bus not available</b>')
    dialog.format_secondary_text('OpenVPN Indicator requires D-Bus to run. Please install required libraries.')

    def on_dialog_response(_object, response):
        dialog.destroy()

    dialog.connect('response', on_dialog_response)
    dialog.show_all()
    return dialog


def construct_openvpn_missing_dialog():
    dialog = Gtk.MessageDialog()
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
    dialog.set_markup('<b>OpenVPN3 not available</b>')
    dialog.format_secondary_text('OpenVPN Indicator requires OpenVPN3 python library to run. Please install OpenVPN3.')

    def on_dialog_response(_object, response):
        dialog.destroy()

    dialog.connect('response', on_dialog_response)
    dialog.show_all()
    return dialog


def construct_secret_storage_missing_dialog():
    dialog = Gtk.MessageDialog()
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
    dialog.set_markup('<b>Secret Storage not available</b>')
    dialog.format_secondary_text('OpenVPN Indicator requires Secret Storage to run. Please install required libraries.')

    def on_dialog_response(_object, response):
        dialog.destroy()

    dialog.connect('response', on_dialog_response)
    dialog.show_all()
    return dialog
