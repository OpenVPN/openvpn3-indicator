#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

#
# openvpn3-indicator - Simple GTK indicator GUI for OpenVPN3.
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

import argparse
import gettext
import logging
import sys
import time
import traceback
import uuid

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, GObject, Gtk, Gio
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
import webbrowser

import openvpn3

from openvpn3_indicator.about import *
from openvpn3_indicator.multi_indicator import MultiIndicator
from openvpn3_indicator.multi_notifier import MultiNotifier
from openvpn3_indicator.credential_store import CredentialStore

#TODO: Present session state (change icon on errors, etc.)
#TODO: Notify user on some of the session state changes
#TODO: Ask for user confirmation when removing config (and maybe in some other places?)
#TODO: Collect and present session logs and stats
#TODO: Understand better the possible session state changes
#TODO: Implement other than AppIndicator ways to have system tray icon
#TODO: /usr/share/metainfo ?
#TODO: Understand mimetype icons inheritance
#TODO: Prepare localization

DEFAULT_CONFIG_NAME = gettext.gettext('UNKNOWN')
DEFAULT_SESSION_NAME = gettext.gettext('UNKNOWN')

###
#
# Application
#
###

class Application(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self,
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
            )
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show version and exit", None)
        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show more info", None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show debug info", None)
        self.add_main_option('silent', ord('s'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show less info", None)
        self.connect('handle-local-options', self.on_local_options)
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.connect('open', self.on_open)

    def on_local_options(self, application, options):
        options = options.end().unpack()
        level=logging.WARNING
        if options.get('version', False):
            print(f'{APPLICATION_NAME} {APPLICATION_VERSION}')
            return 0
        if options.get('debug', False):
            level = logging.DEBUG
        elif options.get('silent', False):
            level = logging.INFO
        elif options.get('verbose', False):
            level = logging.ERROR
        logging.basicConfig(level = level)
        return -1

    def on_activate(self, data):
        logging.info(f'Activate')

    def on_open(self, application, files, n_files, hint):
        logging.info(f'Open {n_files} {hint}')
        for file in files:
            config_path = file.get_path()
            self.action_config_open(config_path)

    def on_startup(self, data):
        logging.info(f'Startup')
        DBusGMainLoop(set_as_default=True)
        self.dbus = dbus.SystemBus()
        #self.dbus = self.get_dbus_connection()
        self.config_manager = openvpn3.ConfigurationManager(self.dbus)
        self.session_manager = openvpn3.SessionManager(self.dbus)
        self.session_manager.SessionManagerCallback(self.on_session_manager_event)
        #TODO: What can you do with Network Change Events?
        #self.network_manager = openvpn3.NetCfgManager(self.dbus)
        #self.network_manager.SubscribeNetworkChange(self.on_network_manager_event)

        self.credential_store = CredentialStore()

        self.configs = dict()
        self.sessions = dict()
        self.config_names = dict()
        self.name_configs = dict()
        self.config_sessions = dict()
        self.session_configs = dict()
        self.session_failed_authentications = set()
        self.session_dialogs = dict()
        self.session_statuses = dict()

        self.multi_indicator = MultiIndicator(f'{APPLICATION_NAME}')
        self.default_indicator = self.multi_indicator.new_indicator()
        self.default_indicator.icon=f'{APPLICATION_NAME}-idle'
        self.default_indicator.description=f'{APPLICATION_DESCRIPTION}'
        self.default_indicator.title=f'{APPLICATION_DESCRIPTION}'
        self.default_indicator.order_key='0'
        self.default_indicator.active=True
        self.indicators = dict()
        
        self.multi_notifier = MultiNotifier(self, f'{APPLICATION_NAME}')
        self.notifiers = dict()

        self.last_invalid = time.monotonic()
        self.invalid_sessions = True
        self.invalid_ui = True

        GLib.timeout_add(1000, self.on_schedule)
        self.hold()

        self.multi_notifier.new_notifier(
            identifier = 'startup',
            title = f'{APPLICATION_DESCRIPTION}',
            body = 'Started',
            icon = f'{APPLICATION_NAME}',
            active = True,
            timespan = 2,
        )

    def refresh_ui(self):
        if self.invalid_ui:
            new_indicators = dict()
            for session_id in self.sessions:
                indicator = self.indicators.get(session_id, None)
                if indicator is None:
                    session_name = self.get_session_name(session_id)
                    indicator = self.multi_indicator.new_indicator()
                    indicator.icon = f'{APPLICATION_NAME}-active'
                    indicator.description = f'{APPLICATION_DESCRIPTION}: {session_name}'
                    indicator.title = f'{APPLICATION_DESCRIPTION}: {session_name}'
                    indicator.order_key = f'1-{session_name}-{session_id}'
                    indicator.active = True
                new_indicators[session_id] = indicator
            new_notifiers = dict()
            for session_id in self.sessions:
                notifier = self.notifiers.get(session_id, None)
                if notifier is None:
                    session_name = self.get_session_name(session_id)
                    notifier = self.multi_notifier.new_notifier(f'session-{session_id}-status')
                    notifier.icon = '{APPLICATION_NAME}-active'
                    notifier.title = f'{APPLICATION_DESCRIPTION}: {session_name}'
                    notifier.title = session_name
                    notifier.active = False
                new_notifiers[session_id] = notifier
            for session_id, indicator in self.indicators.items():
                if session_id not in new_indicators:
                    indicator.close()
            for session_id, notifier in self.notifiers.items():
                if session_id not in new_notifiers:
                    notifier.close()
            if len(new_indicators) == 0:
                self.default_indicator.active = True
                #TODO: Change icon, description, etc. Based on what?
                self.default_indicator.menu = self.construct_idle_menu()
            else:
                self.default_indicator.active = False
            self.indicators = new_indicators
            for session_id, indicator in self.indicators.items():
                if session_id is not None:
                    #TODO: Change icon, description, etc. based on status
                    indicator.menu = self.construct_session_menu(session_id)
            self.multi_indicator.update()
            self.notifiers = new_notifiers
            self.invalid_ui = False

    def refresh_sessions(self):
        if self.invalid_sessions:
            try:
                new_session_ids = set()
                new_sessions = dict()
                for session in self.session_manager.FetchAvailableSessions():
                    session_id = str(session.GetPath())
                    if session_id not in self.sessions:
                        new_sessions[session_id] = session
                        session.StatusChangeCallback(lambda major, minor, message: self.on_session_event(session_id, major, minor, message))
                        new_session_ids.add(session_id)
                    else:
                        new_sessions[session_id] = self.sessions[session_id]
                new_configs = dict()
                for config in self.config_manager.FetchAvailableConfigs():
                    config_id = str(config.GetPath())
                    if config_id not in self.configs:
                        new_configs[config_id] = config
                    else:
                        new_configs[config_id] = self.configs[config_id]
                new_config_names = dict()
                for config_id, config in new_configs.items():
                    config_name = str(config.GetConfigName())
                    new_config_names[config_id] = config_name
                new_config_sessions = dict()
                new_session_configs = dict()
                for config_id, config_name in new_config_names.items():
                    new_config_sessions[config_id] = list()
                    for session_id in self.session_manager.LookupConfigName(config_name):
                        session_id = str(session_id)
                        new_config_sessions[config_id].append(session_id)
                        new_session_configs[session_id] = config_id
                new_session_statuses = dict()
                for session_id, session in new_sessions.items():
                    status = session.GetStatus()
                    new_session_statuses[session_id] = {
                        'major' : openvpn3.StatusMajor(status['major']),
                        'minor' : openvpn3.StatusMinor(status['minor']),
                        'message' : str(status['message']),
                    }
                self.sessions = new_sessions
                self.configs = new_configs
                self.config_names = new_config_names
                self.name_configs = dict([(value, key) for key,value in new_config_names.items()])
                self.config_sessions = new_config_sessions
                self.session_configs = new_session_configs
                self.session_statuses = new_session_statuses

                logging.debug(f'Configs: {sorted(self.configs.keys())}')
                logging.debug(f'Sessions: {sorted(self.sessions.keys())}')
                logging.debug(f'Config names: {self.config_names}')
                logging.debug(f'Config sessions: {self.config_sessions}')
                logging.debug(f'Session configs: {self.session_configs}')
                logging.debug(f'Session statuses: {self.session_statuses}')
                self.invalid_sessions = False
                self.invalid_ui = True
            except: #TODO: Catch only expected exceptions
                logging.debug(traceback.format_exc())
                logging.warning(f'Session list refresh failed')
            for session_id in new_session_ids:
                session_status = self.session_statuses[session_id]
                self.on_session_event(session_id, session_status['major'], session_status['minor'], session_status['message'])
            for session_id, dialog in list(self.session_dialogs.items()):
                if session_id not in self.sessions:
                    dialog.destroy()
                    if session_id not in self.sessions:
                        del self.session_dialogs[session_id]

    def get_config_name(self, config_id):
        return self.config_names.get(config_id, DEFAULT_CONFIG_NAME)

    def get_session_name(self, session_id):
        return self.get_config_name(self.session_configs.get(session_id, ''))

    def construct_menu_config(self, config_id):
        menu = Gtk.Menu()
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Connect'))
        menu_item.connect('activate', self.action_config_connect, config_id)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Remove'))
        menu_item.connect('activate', self.action_config_remove, config_id)
        menu.append(menu_item)
        return menu

    def construct_menu_session(self, session_id):
        menu = Gtk.Menu()
        status = self.session_statuses[session_id]
        major = status['major']
        minor = status['minor']
        menu_item = Gtk.MenuItem.new_with_label(self.get_session_name(session_id))
        menu.append(menu_item)

        if False: #TODO: When does it make sense to allow explicit Connect?
            menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Connect'))
            menu_item.connect('activate', self.action_session_connect, session_id)
            menu.append(menu_item)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_CONNECTED == minor:
            menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Pause'))
            menu_item.connect('activate', self.action_session_pause, session_id)
            menu.append(menu_item)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_PAUSED == minor:
            menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Resume'))
            menu_item.connect('activate', self.action_session_resume, session_id)
            menu.append(menu_item)
        if True:
            menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Restart'))
            menu_item.connect('activate', self.action_session_restart, session_id)
            menu.append(menu_item)
        if True:
            menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Disconnect'))
            menu_item.connect('activate', self.action_session_disconnect, session_id)
            menu.append(menu_item)
        return menu

    def construct_session_menu(self, session_id):
        menu = self.construct_menu_session(session_id)
        menu.append(Gtk.SeparatorMenuItem())
        add_separator = False
        for config_name, config_id in sorted(self.name_configs.items()):
            if len(self.config_sessions[config_id]) == 0:
                config_menu = self.construct_menu_config(config_id)
                menu_item = Gtk.MenuItem.new_with_label(config_name)
                menu_item.set_submenu(config_menu)
                menu.append(menu_item)
                add_separator = True
        if add_separator:
            menu.append(Gtk.SeparatorMenuItem())
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Import Config'))
        menu_item.connect('activate', self.action_config_import)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('About'))
        menu_item.connect('activate', self.action_about)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Quit'))
        menu_item.connect('activate', self.action_quit)
        menu.append(menu_item)
        menu.show_all()
        return menu

    def construct_idle_menu(self):
        menu = Gtk.Menu()
        for config_name, config_id in sorted(self.name_configs.items()):
            session_ids = self.config_sessions[config_id]
            if len(session_ids) > 0:
                for session_id in session_ids:
                    #TODO: Add some information on session status to menu items (perhaps in the title?)
                    session = self.sessions[session_id]
                    session_menu = self.construct_menu_session(config_id, session_id)
                    menu_item = Gtk.MenuItem.new_with_label(config_name)
                    menu_item.set_submenu(session_menu)
                    menu.append(menu_item)
            else:
                config_menu = self.construct_menu_config(config_id)
                menu_item = Gtk.MenuItem.new_with_label(config_name)
                menu_item.set_submenu(config_menu)
                menu.append(menu_item)
        if len(self.name_configs) > 0:
            menu.append(Gtk.SeparatorMenuItem())
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Import Config'))
        menu_item.connect('activate', self.action_config_import)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('About'))
        menu_item.connect('activate', self.action_about)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Quit'))
        menu_item.connect('activate', self.action_quit)
        menu.append(menu_item)
        menu.show_all()
        return menu

    def session_icon(self, session_id):
        status = self.session_statuses[session_id]
        major = status['major']
        minor = status['minor']
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_OK == minor:
            return f'{APPLICATION_NAME}-configuring'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_URL == minor:
            return f'{APPLICATION_NAME}-configuring'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.PROC_STOPPED == minor:
            return f'{APPLICATION_NAME}-active-error'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_AUTH_FAILED == minor:
            return f'{APPLICATION_NAME}-idle-error'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_FAILED == minor:
            return f'{APPLICATION_NAME}-idle-error'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DISCONNECTED == minor:
            return f'{APPLICATION_NAME}-idle'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DONE == minor:
            return f'{APPLICATION_NAME}-idle'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
            return f'{APPLICATION_NAME}-configuring'
        return f'{APPLICATION_NAME}-active'

    def session_description(self, session_id):
        status = self.session_statuses[session_id]
        major = status['major']
        minor = status['minor']
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_OK == minor:
            return f'Configuration OK'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_URL == minor:
            return f'Authentication required'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.PROC_STOPPED == minor:
            return f'Stopped'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_AUTH_FAILED == minor:
            return f'Authentication failed'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_FAILED == minor:
            return f'Connection failed'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DISCONNECTED == minor:
            return f'Disconnected'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DONE == minor:
            return f'Done'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
            return f'Authentication required'
        return f'Connected'

    def notify_session_change(self, session_id):
        indicator = self.indicators.get(session_id, None)
        if indicator:
            indicator.icon = self.session_icon(session_id)
        notifier = self.notifiers.get(session_id, None)
        if notifier:
            notifier.active = False
            notifier.icon = self.session_icon(session_id)
            notifier.body = self.session_description(session_id)
            notifier.timespan = 3
            notifier.active = True

    def on_session_manager_event(self, event):
        logging.info(f'Session Manager Event {event}')
        event_type = event.GetType()
        if openvpn3.SessionManagerEventType.SESS_CREATED == event_type:
            self.invalid_sessions = True
        elif openvpn3.SessionManagerEventType.SESS_DESTROYED == event_type:
            self.invalid_sessions = True

    def on_network_manager_event(self, event):
        logging.info(f'Network Manager Event {event}')

    def on_session_event(self, session_id, major, minor, message):
        major = openvpn3.StatusMajor(major)
        minor = openvpn3.StatusMinor(minor)
        message = str(message)
        logging.info(f'Session Event {major} {minor} {message}')
        self.session_statuses[session_id] = {
            'major' : major,
            'minor' : minor,
            'message' : message,
        }
        self.invalid_ui = True

        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_OK == minor:
            pass
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_URL == minor:
            self.action_auth_url(None, session_id, message)
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.PROC_STOPPED == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_AUTH_FAILED == minor:
            #TODO: Notify authentication failure
            #TODO: Record authentication failure
            self.action_session_disconnect(None, session_id)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_FAILED == minor:
            #TODO: Notify connection failure
            #TODO: Record connection failure
            self.action_session_disconnect(None, session_id)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DISCONNECTED == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DONE == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
            session = self.sessions[session_id]
            try:
                required_credentials = list()
                for input_slot in session.FetchUserInputSlots():
                    if input_slot.GetTypeGroup()[0] != openvpn3.ClientAttentionType.CREDENTIALS:
                        continue
                    description = str(input_slot.GetLabel())
                    mask = bool(input_slot.GetInputMask())
                    required_credentials.append((description, mask))
            except: #TODO: Catch only expected exceptions
                logging.debug(traceback.format_exc())
                #TODO: Catch only expected exceptions
                #TODO: Notify authentication failure
                #TODO: Record authentication failure
                self.action_session_disconnect(None, session_id)

            self.action_get_credentials(None, session_id, required_credentials)#, force_ui=True)
        self.notify_session_change(session_id)

    def action_auth_url(self, _object, session_id, url):
        webbrowser.open_new(url)

    def store_set_credentials(self, config_id, credentials):
        store = self.credential_store[config_id]
        for key, value in credentials.items():
            store[key] = value

    def store_clear_credentials(self, config_id):
        store = self.credential_store[config_id]
        for key in store.keys():
            del store[key]

    def store_get_credentials(self, config_id):
        credentials = dict()
        store = self.credential_store[config_id]
        for key in store.keys():
            credentials[key] = store[key]
        return credentials

    def action_get_credentials(self, _object, session_id, required_credentials, force_ui=False):
        credentials = dict()
        required_keys = set([ description for description, mask in required_credentials ])
        config_id = self.session_configs.get(session_id, None)
        if config_id is not None:
            for key, value in self.store_get_credentials(config_id).items():
                if key in required_keys:
                    credentials[key] = value

        require_ui = False
        for key in required_keys:
            if key not in credentials:
                require_ui = True
                break

        if require_ui or force_ui:
            dialog = Gtk.Dialog(gettext.gettext('OpenVPN Credentials'))
            dialog.add_buttons(Gtk.STOCK_CONNECT, Gtk.ResponseType.ACCEPT, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            dialog.set_icon_name(APPLICATION_NAME)
            dialog.set_position(Gtk.WindowPosition.CENTER)
            content_area = dialog.get_content_area()
            content_area.set_property('hexpand', True)
            content_area.set_property('vexpand', True)
            grid = Gtk.Grid(row_spacing=10, column_spacing=10, vexpand=True, hexpand=True, margin_top=20, margin_right=20, margin_bottom=20, margin_left=20)
            session_name = self.get_session_name(session_id)
            introduction = f'Session {session_name} requires providing credentials'
            grid.attach(Gtk.Label(label=introduction, hexpand=True), 0, 0, 2, 1)
            row = 1
            entries = dict()
            for description, mask in required_credentials:
                label = Gtk.Label(label=description, hexpand=True, xalign=0, margin_right=10)
                grid.attach(label, 0, row, 1, 1)
                entry = Gtk.Entry(hexpand=True)
                if mask:
                    entry.set_visibility(False)
                if description in credentials:
                    entry.set_text(credentials[description])
                grid.attach(entry, 1, row, 1, 1)
                entries[description] = entry
                row += 1
            store_button = Gtk.CheckButton(label='Store credentials', hexpand=True)
            if len(credentials) > 0:
                store_button.set_active(True)
            else:
                store_button.set_active(False)
            grid.attach(store_button, 0, row, 2, 1)
            content_area.add(grid)

            def on_destroy(_object):
                self.action_session_disconnect(None, session_id)
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
            dialog.connect('destroy', on_destroy)
            def on_response(_object, response):
                if response == Gtk.ResponseType.CANCEL:
                    self.action_session_disconnect(None, session_id)
                    self.session_dialogs[session_id].disconnect_by_func(on_destroy)
                    self.session_dialogs[session_id].destroy()
                    if session_id in self.session_dialogs:
                        del self.session_dialogs[session_id]
                    return
                credentials = dict()
                for description, entry in entries.items():
                    credentials[description] = entry.get_text()
                    if not credentials[description]:
                        return
                if store_button.get_active():
                    self.store_set_credentials(config_id, credentials)
                else:
                    self.store_clear_credentials(config_id)
                self.session_dialogs[session_id].disconnect_by_func(on_destroy)
                self.session_dialogs[session_id].destroy()
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
                self.on_session_credentials(session_id, credentials)
            dialog.connect('response', on_response)
            dialog.set_keep_above(True)
            dialog.show_all()
            if session_id in self.session_dialogs:
                self.session_dialogs[session_id].destroy()
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
            self.session_dialogs[session_id] = dialog
        else:
            self.on_session_credentials(session_id, credentials)

    def on_session_credentials(self, session_id, credentials):
        session = self.sessions[session_id]
        try:
            for input_slot in session.FetchUserInputSlots():
                if input_slot.GetTypeGroup()[0] != openvpn3.ClientAttentionType.CREDENTIALS:
                    continue
                input_slot.ProvideInput(credentials.get(input_slot.GetLabel(), ''))
            session.Connect()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            self.action_session_disconnect(None, session_id)

    def on_schedule(self):
        logging.debug(f'Schedule')
        if self.last_invalid + 30 < time.monotonic():
            logging.debug('ref')
            self.invalid_sessions = True
        if self.invalid_sessions:
            self.last_invalid = time.monotonic()
            self.refresh_sessions()
        if self.invalid_ui:
            self.refresh_ui()
        self.multi_notifier.update()
        GLib.timeout_add(1000, self.on_schedule)

    def action_config_connect(self, _object, config_id):
        logging.info(f'Connect Config {config_id}')
        if config_id not in self.configs:
            return
        try:
            self.session_manager.NewTunnel(self.configs[config_id])
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_config_remove(self, _object, config_id):
        logging.info(f'Connect Config {config_id}')
        if config_id not in self.configs:
            return
        try:
            self.configs[config_id].Remove()
            self.invalid_sessions = True
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_session_connect(self, _object, session_id):
        logging.info(f'Connect Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Connect()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_session_pause(self, _object, session_id):
        logging.info(f'Pause Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Pause()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_session_resume(self, _object, session_id):
        logging.info(f'Resume Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Resume()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_session_restart(self, _object, session_id):
        logging.info(f'Restart Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Restart()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_session_disconnect(self, _object, session_id):
        logging.info(f'Disconnect Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Disconnect()
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_config_import(self, _object):
        logging.info(f'Import Config')
        dialog = Gtk.FileChooserDialog(action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )
        dialog.set_icon_name(APPLICATION_NAME)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.set_keep_above(True)
        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            config_path = dialog.get_filename()
            dialog.destroy()

            self.action_config_open(config_path)

        else:
            dialog.destroy()

    def action_config_open(self, config_path):
        #TODO: Deduce default config_name from config content
        config_name = 'NEW'
        #TODO: Hide single_use and persistent from interface?
        config_single_use = False
        config_persistent = True
        dialog2 = Gtk.Dialog()
        dialog2 = Gtk.Dialog(gettext.gettext('OpenVPN Configuration Import'))
        dialog2.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog2.set_icon_name(APPLICATION_NAME)
        dialog2.set_position(Gtk.WindowPosition.CENTER)
        content_area = dialog2.get_content_area()
        content_area.set_property('hexpand', True)
        content_area.set_property('vexpand', True)
        grid = Gtk.Grid(row_spacing=10, column_spacing=10, vexpand=True, hexpand=True, margin_top=20, margin_right=20, margin_bottom=20, margin_left=20)
        grid.attach(Gtk.Label(label=config_path, hexpand=True), 0, 0, 2, 1)
        label = Gtk.Label(label=gettext.gettext('Configuration Name'), hexpand=True, xalign=0, margin_right=10)
        grid.attach(label, 0, 1, 1, 1)
        entry = Gtk.Entry(hexpand=True)
        entry.set_text(config_name)
        grid.attach(entry, 1, 1, 1, 1)
        single_use_button = Gtk.CheckButton(label=gettext.gettext('Single use'), hexpand=True)
        single_use_button.set_active(config_single_use)
        grid.attach(single_use_button, 0, 2, 2, 1)
        persistent_button = Gtk.CheckButton(label=gettext.gettext('Persistent'), hexpand=True)
        persistent_button.set_active(config_persistent)
        grid.attach(persistent_button, 0, 3, 2, 1)
        content_area.add(grid)
        dialog2.set_keep_above(True)
        dialog2.show_all()
        response2 = dialog2.run()
        if response2 == Gtk.ResponseType.OK:
            config_name = entry.get_text()
            config_single_use = single_use_button.get_active()
            config_persistent = persistent_button.get_active()
            self.action_config_import_path(None, config_name, config_path, config_single_use, config_persistent)
        dialog2.destroy()

    def action_config_import_path(self, _object, config_name, config_path, config_single_use, config_persistent):
        logging.info(f'Import Config Path')
        try:
            parser = openvpn3.ConfigParser(['openvpn3-indicator-config-parser', '--config', config_path], '')
            config_description = parser.GenerateConfig()
            self.config_manager.Import(config_name, config_description, config_single_use, config_persistent)
            self.invalid_sessions = True
        except: #TODO: Catch only expected exceptions
            logging.debug(traceback.format_exc())
            pass

    def action_about(self, _object):
        logging.info(f'About')
        webbrowser.open_new(APPLICATION_URL)

    def action_quit(self, _object):
        logging.info(f'Quit')
        self.release()
