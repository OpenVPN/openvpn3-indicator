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

###
#
# Main
#
###


def main(args=None):
    import logging
    import sys
    import traceback
    from openvpn3_indicator.about import APPLICATION_NAME
    from openvpn3_indicator.application import Application

    try:
        import setproctitle
        setproctitle.setproctitle(f'{APPLICATION_NAME}')
    except ImportError:
        logging.debug(traceback.format_exc())
        logging.error('Failed to import setproctitle module')

    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import GLib, GObject, Gtk, Gio
    except:
        logging.critical('OpenVPN Indicator requires GTK to run. Please install required libraries.')
        sys.exit(1)

    from openvpn3_indicator.dialogs.system_checks import construct_dbus_missing_dialog, construct_appindicator_missing_dialog, construct_openvpn_missing_dialog, construct_secret_storage_missing_dialog
    
    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
    except:
        logging.critical('OpenVPN Indicator requires D-Bus to run. Please install required libraries.')
        dialog = construct_dbus_missing_dialog()
        dialog.set_visible(True)
        dialog.run()
        sys.exit(1)

    try:
        try:
            gi.require_version('AyatanaAppIndicator3', '0.1')
            from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        except:
            gi.require_version('AppIndicator3', '0.1')
            from gi.repository import AppIndicator3
    except:
        logging.critical('OpenVPN Indicator requires AppIndicator to run. Please install AppIndicator plugin for your desktop.')
        dialog = construct_appindicator_missing_dialog()
        dialog.set_visible(True)
        dialog.run()
        sys.exit(1)

    try:
        import openvpn3
    except:
        logging.critical('OpenVPN Indicator requires OpenVPN3 python library to run. Please install OpenVPN3.')
        dialog = construct_openvpn_missing_dialog()
        dialog.set_visible(True)
        dialog.run()
        sys.exit(1)

    try:
        import secretstorage
    except:
        logging.critical('OpenVPN Indicator requires Secret Storage to run. Please install required libraries.')
        dialog = construct_secret_storage_missing_dialog()
        dialog.set_visible(True)
        dialog.run()
        sys.exit(1)

    application = Application()
    if args is None:
        args = sys.argv
    application.run(args)


if __name__ == '__main__':
    main()
