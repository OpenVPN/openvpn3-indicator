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
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import APPLICATION_NAME

def construct_notification_dialog(parent=None, title=None, message=None, message_type=Gtk.MessageType.INFO):
    dialog = Gtk.MessageDialog(
        parent=parent,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        type=message_type,
        buttons=Gtk.ButtonsType.OK
    )

    if title:
        dialog.set_title(title)
    else:
        type_names = {
            Gtk.MessageType.INFO: "Info",
            Gtk.MessageType.WARNING: "Warning", 
            Gtk.MessageType.ERROR: "Error",
            Gtk.MessageType.QUESTION: "Question"
        }
        type_name = type_names.get(message_type, "Notification")
        dialog.set_title(f"{APPLICATION_NAME} - {type_name}")

    if message:
        dialog.set_markup(GLib.markup_escape_text(message))

    return dialog


def show_notification_dialog(parent=None, title=None, message=None, message_type=Gtk.MessageType.INFO):
    dialog = construct_notification_dialog(parent, title, message, message_type)
    response = dialog.run()
    dialog.destroy()
    return response


def show_info_notification(parent=None, title=None, message=None):
    return show_notification_dialog(parent, title, message, Gtk.MessageType.INFO)


def show_warning_notification(parent=None, title=None, message=None):
    return show_notification_dialog(parent, title, message, Gtk.MessageType.WARNING)


def show_error_notification(parent=None, title=None, message=None):
    return show_notification_dialog(parent, title, message, Gtk.MessageType.ERROR)


def show_question_notification(parent=None, title=None, message=None):
    dialog = Gtk.MessageDialog(
        parent=parent,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
        type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO
    )

    if title:
        dialog.set_title(title)
    else:
        dialog.set_title(f"{APPLICATION_NAME} - Question")

    if message:
        dialog.set_markup(GLib.markup_escape_text(message))

    response = dialog.run()
    dialog.destroy()
    return response


def construct_error_dialog(parent=None, title=None, message=None):
    return construct_notification_dialog(parent, title, message, Gtk.MessageType.ERROR)


def show_error_dialog(parent=None, title=None, message=None):
    return show_error_notification(parent, title, message)