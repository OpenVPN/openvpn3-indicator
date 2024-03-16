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

from openvpn3_indicator.about import APPLICATION_NAME

DEFAULT_CONFIG_NAME = 'NEW'

def construct_configuration_select_dialog(name=None, on_import=None, on_cancel=None):
    dialog = Gtk.FileChooserDialog(action=Gtk.FileChooserAction.OPEN)
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            'Import', Gtk.ResponseType.OK,
        )
    ovpn_filter = Gtk.FileFilter()
    ovpn_filter.set_name('OpenVPN Configuration Files')
    ovpn_filter.add_mime_type('application/x-openvpn-profile')
    dialog.add_filter(ovpn_filter)
    text_filter = Gtk.FileFilter()
    text_filter.set_name('Text Files')
    text_filter.add_mime_type('text/plain')
    dialog.add_filter(text_filter)
    all_filter = Gtk.FileFilter()
    all_filter.set_name('All Files')
    all_filter.add_pattern('*')
    dialog.add_filter(all_filter)
    dialog.set_show_hidden(False)
    dialog.set_filter(ovpn_filter)

    def on_dialog_destroy(_object):
        if on_cancel is not None:
            on_cancel()

    def on_dialog_response(_object, response):
        if response == Gtk.ResponseType.OK:
            dialog.disconnect_by_func(on_dialog_destroy)
            configuration_path = dialog.get_filename()
            import_dialog = construct_configuration_import_dialog(name=name, path=configuration_path, on_import=on_import, on_cancel=on_cancel)
            import_dialog.set_visible(True)
        dialog.destroy()

    dialog.connect('destroy', on_dialog_destroy)
    dialog.connect('response', on_dialog_response)
    dialog.show_all()
    return dialog


def construct_configuration_import_dialog(path, name=None, on_import=None, on_cancel=None):
    name = name or DEFAULT_CONFIG_NAME
    dialog = Gtk.Dialog('OpenVPN Configuration Import')
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            'Import', Gtk.ResponseType.OK,
        )
    content_area = dialog.get_content_area()
    content_area.set_property('hexpand', True)
    content_area.set_property('vexpand', True)
    grid = Gtk.Grid(row_spacing=10, column_spacing=10, vexpand=True, hexpand=True, margin_top=20, margin_right=20, margin_bottom=20, margin_left=20)

    grid.attach(Gtk.Label(label='Configuration File', hexpand=True, xalign=0, margin_right=10), 0, 0, 1, 1)
    grid.attach(Gtk.Label(label=path, hexpand=True), 1, 0, 1, 1)
    
    grid.attach(Gtk.Label(label='Configuration Name', hexpand=True, xalign=0, margin_right=10), 0, 1, 1, 1)
    entry = Gtk.Entry(hexpand=True)
    entry.set_text(name)
    entry.set_activates_default(True)
    grid.attach(entry, 1, 1, 1, 1)

    content_area.add(grid)

    def on_dialog_destroy(_object):
        if on_cancel is not None:
            on_cancel()

    def on_dialog_response(_object, response):
        if response == Gtk.ResponseType.OK:
            dialog.disconnect_by_func(on_dialog_destroy)
            if on_import is not None:
                name = entry.get_text()
                on_import(name=name, path=path)
        dialog.destroy()

    dialog.connect('destroy', on_dialog_destroy)
    dialog.connect('response', on_dialog_response)
    default = dialog.get_widget_for_response(response_id=Gtk.ResponseType.OK)
    default.set_can_default(True)
    default.grab_default()
    dialog.show_all()
    return dialog


def construct_configuration_remove_dialog(name, on_remove=None, on_cancel=None):
    dialog = Gtk.Dialog('OpenVPN Configuration Remove')
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            'Remove', Gtk.ResponseType.OK,
        )
    content_area = dialog.get_content_area()
    content_area.set_property('hexpand', True)
    content_area.set_property('vexpand', True)
    grid = Gtk.Grid(row_spacing=10, column_spacing=10, vexpand=True, hexpand=True, margin_top=20, margin_right=20, margin_bottom=20, margin_left=20)

    grid.attach(Gtk.Label(label=f'You are about to remove configuration {name}', hexpand=True, xalign=0, margin_right=10), 0, 0, 1, 1)

    content_area.add(grid)

    def on_dialog_destroy(_object):
        if on_cancel is not None:
            on_cancel()

    def on_dialog_response(_object, response):
        if response == Gtk.ResponseType.OK:
            dialog.disconnect_by_func(on_dialog_destroy)
            if on_remove is not None:
                on_remove()
        dialog.destroy()

    dialog.connect('destroy', on_dialog_destroy)
    dialog.connect('response', on_dialog_response)
    default = dialog.get_widget_for_response(response_id=Gtk.ResponseType.OK)
    default.set_can_default(True)
    default.grab_default()
    dialog.show_all()
    dialog.show_all()
    return dialog
