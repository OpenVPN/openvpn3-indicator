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

import collections

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, GObject, Gtk, Gio

from openvpn3_indicator.about import APPLICATION_NAME


CredentialsUserInput = collections.namedtuple(
        'CredentialsUserInput',
        ['name', 'mask', 'value', 'can_store']
    )


def construct_credentials_dialog(name, user_inputs, allow_store=True, on_connect=None, on_cancel=None, remain_active=None):
    dialog = Gtk.Dialog('OpenVPN Credentials')
    dialog.set_position(Gtk.WindowPosition.CENTER)
    dialog.set_keep_above(True)
    dialog.set_icon_name(APPLICATION_NAME)
    dialog.add_buttons(
            Gtk.STOCK_CONNECT, Gtk.ResponseType.OK,
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        )
    content_area = dialog.get_content_area()
    content_area.set_property('hexpand', True)
    content_area.set_property('vexpand', True)
    grid = Gtk.Grid(row_spacing=10, column_spacing=10, vexpand=True, hexpand=True, margin_top=20, margin_right=20, margin_bottom=20, margin_left=20)
    introduction = f'Session {name} requires providing credentials'
    grid.attach(Gtk.Label(label=introduction, hexpand=True, margin_bottom=10), 0, 0, 2, 1)
    row = 1
    entries = list()
    default_store = False
    can_store = False
    for user_input in user_inputs:
        label = Gtk.Label(label=user_input.name, hexpand=True, xalign=0, margin_right=10)
        grid.attach(label, 0, row, 1, 1)
        entry = Gtk.Entry(hexpand=True)
        if user_input.mask:
            entry.set_visibility(False)
        if user_input.can_store:
            can_store = True
        if user_input.value is not None:
            entry.set_text(user_input.value)
            default_store = True
        entry.set_activates_default(True)
        grid.attach(entry, 1, row, 1, 1)
        entries.append(entry)
        row += 1
    if can_store and allow_store:
        store_button = Gtk.CheckButton(label='Store credentials', hexpand=True, margin_top=10)
        store_button.set_active(default_store)
        grid.attach(store_button, 0, row, 2, 1)
    content_area.add(grid)

    def on_dialog_destroy(_object):
        if on_cancel is not None:
            on_cancel()

    def on_dialog_response(_object, response):
        if response == Gtk.ResponseType.OK:
            dialog.disconnect_by_func(on_dialog_destroy)
            if on_connect is not None:
                results = list()
                for user_input, entry in zip(user_inputs, entries):
                    results.append(CredentialsUserInput(name=user_input.name, mask=user_input.mask, value=entry.get_text(), can_store=user_input.can_store))
                store = None
                if can_store and allow_store:
                    store = store_button.get_active()
                on_connect(user_inputs=results, store=store)
        dialog.destroy()

    def on_schedule():
        if remain_active():
            GLib.timeout_add(1000, on_schedule)
        else:
            try:
                dialog.disconnect_by_func(on_dialog_destroy)
                dialog.destroy()
            except:
                pass

    dialog.connect('destroy', on_dialog_destroy)
    dialog.connect('response', on_dialog_response)
    default = dialog.get_widget_for_response(response_id=Gtk.ResponseType.OK)
    default.set_can_default(True)
    default.grab_default()
    dialog.show_all()
    if remain_active is not None:
        GLib.timeout_add(1000, on_schedule)
    return dialog
