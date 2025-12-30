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

import gettext
import logging
import pathlib
import re
import sys
import time
import traceback
import webbrowser

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, GObject, Gtk, Gio

import dbus
from dbus.mainloop.glib import DBusGMainLoop
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3

import openvpn3

from openvpn3_indicator.about import APPLICATION_ID, APPLICATION_VERSION, APPLICATION_NAME, APPLICATION_TITLE, APPLICATION_SYSTEM_TAG
from openvpn3_indicator.about import MANAGER_VERSION_MINIMUM, MANAGER_VERSION_RECOMMENDED
from openvpn3_indicator.multi_indicator import MultiIndicator
from openvpn3_indicator.multi_notifier import MultiNotifier
from openvpn3_indicator.credential_store import CredentialStore
from openvpn3_indicator.dialogs.about import construct_about_dialog
from openvpn3_indicator.dialogs.system_checks import construct_appindicator_missing_dialog, construct_openvpn_missing_dialog
from openvpn3_indicator.dialogs.credentials import CredentialsUserInput, construct_credentials_dialog
from openvpn3_indicator.dialogs.configuration import construct_configuration_select_dialog, construct_configuration_import_dialog, construct_configuration_remove_dialog
from openvpn3_indicator.dialogs.notification import show_error_dialog, show_warning_notification, show_info_notification


#TODO: Which input slots should not be stored ? (OTPs, etc.)
#TODO: Understand better the possible session state changes
#TODO: Present session state (change icon on errors, etc.)
#TODO: Notify user on some of the session state changes
#TODO: Collect and present session logs and stats
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
        self.settings = Gio.Settings.new(APPLICATION_ID)
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show version and exit", None)
        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show more info", None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show debug info", None)
        self.add_main_option('silent', ord('s'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Show less info", None)
        self.connect('handle-local-options', self.on_handle_local_options)
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.connect('open', self.on_open)

    def on_handle_local_options(self, application, options):
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
        self.info(f'Activate')

    def on_open(self, application, files, n_files, hint):
        self.info(f'Open {n_files} {hint}')
        for file in files:
            config_path = file.get_path()
            self.action_config_open(config_path)

    def on_startup(self, data):
        self.info(f'Startup')
        DBusGMainLoop(set_as_default=True)

        bus = dbus.Bus()
        notifier_fail_count = 0
        while True:
            try:
                bus.get_name_owner('org.kde.StatusNotifierWatcher')
                break
            except dbus.exceptions.DBusException:
                notifier_fail_count += 1
                if notifier_fail_count > 20:
                    logging.critical('OpenVPN Indicator requires AppIndicator to run. Please install AppIndicator plugin for your desktop.')
                    dialog = construct_appindicator_missing_dialog()
                    dialog.set_visible(True)
                    dialog.run()
                    sys.exit(1)
                else:
                    time.sleep(0.5)

        self.multi_notifier = MultiNotifier(self, f'{APPLICATION_NAME}')
        self.notifiers = dict()

        self.dbus = dbus.SystemBus()
        self.config_manager = openvpn3.ConfigurationManager(self.dbus)
        self.session_manager = openvpn3.SessionManager(self.dbus)
        self.session_manager.SessionManagerCallback(self.on_session_manager_event)

        # Detect if the config manager version is v21 or newer
        # TODO: This can be simplified once the openvpn3 module provides
        #       a version query API
        self.manager_version = 0
        cmgr_obj = self.dbus.get_object('net.openvpn.v3.configuration','/net/openvpn/v3/configuration')
        cmgr_prop = dbus.Interface(cmgr_obj, dbus_interface='org.freedesktop.DBus.Properties')
        cmgr_peer = dbus.Interface(cmgr_obj, dbus_interface='org.freedesktop.DBus.Peer')
        self.manager_version = 9999
        try:
            cmgr_peer.Ping()
            try:
                cmgr_version = str(cmgr_prop.Get('net.openvpn.v3.configuration','version'))
            except dbus.exceptions.DBusException:
                self.debug(f'Waiting for backend to start')
                time.sleep(0.5)
                cmgr_version = str(cmgr_prop.Get('net.openvpn.v3.configuration','version'))
            if cmgr_version.startswith('git:'):
                # development version: presume all features are available
                # and use a high version number
                pass
            elif cmgr_version.startswith('v'):
                # Version identifiers may cary a "release label",
                # like v19_beta, v22_dev
                self.manager_version = int(re.split(r'[^0-9]', cmgr_version[1:], 1)[0])
        except:
            self.debug(traceback.format_exc())
            self.warning(f'Backend version check failed')
        if self.manager_version < MANAGER_VERSION_MINIMUM:
            self.error(f'You are using version {self.manager_version} of OpenVPN3 software which is not supported. Consider an upgrade to a newer version. We recommend version {MANAGER_VERSION_RECOMMENDED}.', notify=True)
        elif self.manager_version < MANAGER_VERSION_RECOMMENDED:
            self.warning(f'You are using version {self.manager_version} of OpenVPN3 software. Consider an upgrade to a newer version. We recommend version {MANAGER_VERSION_RECOMMENDED}.', notify=True)
        self.debug(f'Running with manager version {self.manager_version}')

        self.credential_store = CredentialStore()

        self.configs = dict()
        self.sessions = dict()
        self.sessions_connected = set()
        self.config_names = dict()
        self.name_configs = dict()
        self.config_sessions = dict()
        self.session_configs = dict()
        self.failed_authentications = set()
        self.session_dialogs = dict()
        self.session_statuses = dict()

        self.multi_indicator = MultiIndicator(f'{APPLICATION_NAME}')
        self.default_indicator = self.multi_indicator.new_indicator()
        self.default_indicator.icon=f'{APPLICATION_NAME}-idle'
        self.default_indicator.description=f'{APPLICATION_TITLE}'
        self.default_indicator.title=f'{APPLICATION_TITLE}'
        self.default_indicator.order_key='0'
        self.default_indicator.active=True
        self.indicators = dict()

        self.last_invalid = time.monotonic()
        self.invalid_sessions = True
        self.invalid_ui = True

        self.startup_config_id = None
        self.startup_config_name = None
        try:
            startup_action = self.settings.get_string('startup-action')
            self.debug(f'Startup action: {startup_action}')
            if startup_action == 'RESTART':
                self.startup_config_id = self.settings.get_string('most-recent-configuration-id')
            start_id = re.match(r'STARTID:(?P<id>.*)', startup_action)
            if start_id:
                self.startup_config_id = start_id.group('id')
            start_name = re.match(r'STARTNAME:(?P<name>.*)', startup_action)
            if start_name:
                self.startup_config_name = start_name.group('name')
        except:
            pass
        if self.startup_config_id or self.startup_config_name:
            self.info(f'Startup configuration set to {self.startup_config_id or self.startup_config_name}')

        GLib.timeout_add(1000, self.on_schedule)
        self.hold()

    def refresh_ui(self):
        if self.invalid_ui:
            new_indicators = dict()
            for session_id in self.sessions:
                indicator = self.indicators.get(session_id, None)
                if indicator is None:
                    session_name = self.get_session_name(session_id)
                    indicator = self.multi_indicator.new_indicator()
                    indicator.icon = f'{APPLICATION_NAME}-active'
                    indicator.description = f'{APPLICATION_TITLE}: {session_name}'
                    indicator.title = f'{APPLICATION_TITLE}: {session_name}'
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
                    notifier.title = f'{APPLICATION_TITLE}: {session_name}'
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
            new_session_ids = set()
            try:
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

                self.debug(f'Configs: {sorted(self.configs.keys())}')
                self.debug(f'Sessions: {sorted(self.sessions.keys())}')
                self.debug(f'Config names: {self.config_names}')
                self.debug(f'Config sessions: {self.config_sessions}')
                self.debug(f'Session configs: {self.session_configs}')
                self.debug(f'Session statuses: {self.session_statuses}')
                self.invalid_sessions = False
                self.invalid_ui = True
            except: #TODO: Catch only expected exceptions
                self.debug(traceback.format_exc())
                self.warning(f'Session list refresh failed')
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

    def action_settings_startup(self, _object, value):
        self.settings.set_string('startup-action', value)
        self.invalid_ui = True
        self.refresh_ui()

    def construct_menu_settings_startup(self):
        startup_action = self.settings.get_string('startup-action') or ''
        menu = Gtk.Menu()
        menu_action = ''
        menu_title = gettext.gettext('No Connection')
        if startup_action == menu_action:
            menu_title += ' ✓'
        menu_item = Gtk.MenuItem.new_with_label(menu_title)
        menu_item.connect('activate', self.action_settings_startup, menu_action)
        menu.append(menu_item)
        menu_action = 'RESTART'
        menu_title = gettext.gettext('Restart Connection')
        if startup_action == menu_action:
            menu_title += ' ✓'
        menu_item = Gtk.MenuItem.new_with_label(menu_title)
        menu_item.connect('activate', self.action_settings_startup, menu_action)
        menu.append(menu_item)
        for config_name, config_id in sorted(self.name_configs.items()):
            menu_action = f'STARTNAME:{config_name}'
            menu_title = gettext.gettext('Start {name}').format(name=config_name)
            if startup_action == menu_action:
                menu_title += ' ✓'
            menu_item = Gtk.MenuItem.new_with_label(menu_title)
            menu_item.connect('activate', self.action_settings_startup, menu_action)
            menu.append(menu_item)
        return menu

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
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Startup Settings'))
        menu_item.set_submenu(self.construct_menu_settings_startup())
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
                    session_menu = self.construct_menu_session(session_id)
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
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Startup Settings'))
        menu_item.set_submenu(self.construct_menu_settings_startup())
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
            return f'{APPLICATION_NAME}-loading'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_USERPASS == minor:
            return f'{APPLICATION_NAME}-loading'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_CHALLENGE == minor:
            return f'{APPLICATION_NAME}-loading'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_URL == minor:
            return f'{APPLICATION_NAME}-loading'
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
            return f'{APPLICATION_NAME}-loading'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_PAUSED == minor:
            return f'{APPLICATION_NAME}-paused'
        return f'{APPLICATION_NAME}-active'

    def session_description(self, session_id):
        status = self.session_statuses[session_id]
        major = status['major']
        minor = status['minor']
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_OK == minor:
            return f'Configuration OK'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_USERPASS == minor:
            return f'Authentication required'
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_CHALLENGE == minor:
            return f'Authentication required'
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
            return f'Disconnected'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
            return f'Authentication required'
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_PAUSED == minor:
            return f'Paused'
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
        self.info(f'Session Manager Event {event}')
        event_type = event.GetType()
        if openvpn3.SessionManagerEventType.SESS_CREATED == event_type:
            self.invalid_sessions = True
        elif openvpn3.SessionManagerEventType.SESS_DESTROYED == event_type:
            self.invalid_sessions = True

    def on_network_manager_event(self, event):
        self.info(f'Network Manager Event {event}')

    def can_store_input_slot(self, input_slot):
        type, group = input_slot.GetTypeGroup()
        result = type == openvpn3.ClientAttentionType.CREDENTIALS and group in [
                openvpn3.ClientAttentionGroup.UNSET,
                openvpn3.ClientAttentionGroup.USER_PASSWORD,
                openvpn3.ClientAttentionGroup.HTTP_PROXY_CREDS,
                openvpn3.ClientAttentionGroup.PK_PASSPHRASE,
                #openvpn3.ClientAttentionGroup.CHALLENGE_STATIC,
                #openvpn3.ClientAttentionGroup.CHALLENGE_DYNAMIC,
                #openvpn3.ClientAttentionGroup.CHALLENGE_AUTH_PENDING,
            ]
        self.debug(f'Input slot {input_slot.GetLabel()} of type {type}, group {group} is decided {"not " if not result else ""}safe for storage')
        return result
        print(type,group)

    def on_session_event(self, session_id, major, minor, message):
        session = self.sessions[session_id]
        major = openvpn3.StatusMajor(major)
        minor = openvpn3.StatusMinor(minor)
        message = str(message)
        self.info(f'Session Event {major} {minor} {message}')
        self.session_statuses[session_id] = {
            'major' : major,
            'minor' : minor,
            'message' : message,
        }
        self.invalid_ui = True

        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_OK == minor:
            try:
                if session_id not in self.sessions_connected:
                    session.Ready()
                    session.Connect()
                    self.sessions_connected.add(session_id)
            except: #TODO: Catch only expected exceptions
                self.debug(traceback.format_exc())
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.SESS_AUTH_URL == minor:
            self.action_auth_url(None, session_id, message)
        if openvpn3.StatusMajor.SESSION == major and openvpn3.StatusMinor.PROC_STOPPED == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_AUTH_FAILED == minor:
            #TODO: Notify authentication failure
            #TODO: Record authentication failure

            self.action_session_disconnect(None, session_id)
            config_id = self.session_configs.get(session_id, None)
            if config_id is not None:
                self.failed_authentications.add(config_id)
                self.action_config_connect(None, config_id)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_CONNECTED == minor:
            config_id = self.session_configs.get(session_id, None)
            if config_id is not None and config_id in self.failed_authentications:
                self.failed_authentications.remove(config_id)

        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_FAILED == minor:
            #TODO: Notify connection failure
            #TODO: Record connection failure
            self.action_session_disconnect(None, session_id)
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DISCONNECTED == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CONN_DONE == minor:
            pass
        if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
            try:
                required_credentials = list()
                for input_slot in session.FetchUserInputSlots():
                    if input_slot.GetTypeGroup()[0] != openvpn3.ClientAttentionType.CREDENTIALS:
                        continue
                    description = str(input_slot.GetLabel())
                    mask = bool(input_slot.GetInputMask())
                    can_store = self.can_store_input_slot(input_slot)
                    required_credentials.append((description, mask, can_store))
                force_ui = False
                config_id = self.session_configs.get(session_id, None)
                if config_id is not None:
                    if config_id in self.failed_authentications:
                        force_ui = True
                self.action_get_credentials(None, session_id, required_credentials, force_ui=force_ui)
            except: #TODO: Catch only expected exceptions
                self.debug(traceback.format_exc())
                #TODO: Catch only expected exceptions
                #TODO: Notify authentication failure
                #TODO: Record authentication failure
                self.action_session_disconnect(None, session_id)
        self.notify_session_change(session_id)

    def action_auth_url(self, _object, session_id, url):
        webbrowser.open_new(url)

    def store_set_credentials(self, config_id, credentials):
        store = self.credential_store[config_id]
        for key, value in credentials.items():
            store[key] = value

    def store_clear_credentials(self, config_id, credentials_keys):
        store = self.credential_store[config_id]
        for key in store.keys():
            if key in credentials_keys:
                del store[key]

    def store_get_credentials(self, config_id):
        credentials = dict()
        store = self.credential_store[config_id]
        for key in store.keys():
            credentials[key] = store[key]
        return credentials

    def action_get_credentials(self, _object, session_id, required_credentials, force_ui=False):
        credentials = dict()
        required_keys = set([ description for description, mask, can_store in required_credentials ])
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
            user_inputs = [ CredentialsUserInput(
                    name=description,
                    mask=mask,
                    value=credentials.get(description, None) if can_store else None,
                    can_store=can_store)
                for description, mask, can_store in required_credentials ]


            def on_cancel():
                status = self.session_statuses.get(session_id, None)
                if status is None:
                    return
                major = status['major']
                minor = status['minor']
                if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
                    self.action_session_disconnect(None, session_id)
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]

            def on_connect(user_inputs, store):
                credentials = dict([ (ui.name, ui.value) for ui in user_inputs ])
                if store:
                    store_credentials = dict([ (ui.name, ui.value) for ui in user_inputs if ui.can_store ])
                    self.store_set_credentials(config_id, store_credentials)
                else:
                    self.store_clear_credentials(config_id, credentials.keys())
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
                self.on_session_credentials(session_id, credentials)

            session_name = self.get_session_name(session_id)
            dialog = construct_credentials_dialog(session_name, user_inputs, on_connect=on_connect, on_cancel=on_cancel)
            dialog.set_visible(True)
            if session_id in self.session_dialogs:
                self.session_dialogs[session_id].destroy()
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
            session.Ready()
            session.Connect()
            self.sessions_connected.add(session_id)
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            self.action_session_disconnect(None, session_id)

    def on_schedule(self):
        self.debug(f'Schedule')
        if self.last_invalid + 30 < time.monotonic():
            self.debug('Forced refresh of sessions')
            self.invalid_sessions = True
        if self.invalid_sessions:
            self.last_invalid = time.monotonic()
            self.refresh_sessions()
        if self.invalid_ui:
            self.refresh_ui()
        self.multi_notifier.update()
        if self.startup_config_id or self.startup_config_name:
            config_id = self.startup_config_id or self.name_configs.get(self.startup_config_name, None)
            if config_id and len(self.config_sessions[config_id]) == 0:
                self.debug(f'Starting config {config_id} as requested in startup settings.')
                self.action_config_connect(None, config_id)
            self.startup_config_id = None
            self.startup_config_name = None
        GLib.timeout_add(1000, self.on_schedule)

    def action_config_connect(self, _object, config_id):
        self.info(f'Connect Config {config_id}')
        if config_id not in self.configs:
            return
        try:
            session = self.session_manager.NewTunnel(self.configs[config_id])
            self.settings.set_string('most-recent-configuration-id', config_id)
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_config_remove(self, _object, config_id):
        self.info(f'Remove Config {config_id}')
        if config_id not in self.configs:
            return
        try:
            def on_remove():
                if config_id not in self.configs:
                    return
                self.configs[config_id].Remove()
                self.invalid_sessions = True
            dialog = construct_configuration_remove_dialog(name=self.get_config_name(config_id), on_remove=on_remove)
            dialog.set_visible(True)
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_session_connect(self, _object, session_id):
        self.info(f'Connect Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Connect()
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_session_pause(self, _object, session_id):
        self.info(f'Pause Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Pause()
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_session_resume(self, _object, session_id):
        self.info(f'Resume Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Resume()
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_session_restart(self, _object, session_id):
        self.info(f'Restart Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Restart()
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def action_session_disconnect(self, _object, session_id):
        self.info(f'Disconnect Session {session_id}')
        if session_id not in self.sessions:
            return
        try:
            self.sessions[session_id].Disconnect()
        except: #TODO: Catch only expected exceptions
            self.debug(traceback.format_exc())
            pass

    def on_config_import(self, name, path):
        self.info(f'Import Config {name} {path}')
        try:
            try:
                config_description = pathlib.Path(path).read_text()
            except FileNotFoundError:
                self.error(
                    msg=f"Configuration file not found: {path}",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            except PermissionError:
                self.error(
                    msg=f"Permission denied accessing file: {path}",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            except UnicodeDecodeError:
                self.error(
                    msg=f"File encoding error: {path}\nUnable to read file as text. Please check if this is a valid OpenVPN configuration file.",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            except OSError as e:
                self.error(
                    msg=f"Error reading file: {path}\n{str(e)}",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            try:
                import_args = dict()
                if self.manager_version > 20:
                    # system_tag arrived in openvpn3-linux v21
                    import_args['system_tag'] = APPLICATION_SYSTEM_TAG
                config_obj = self.config_manager.Import(name, config_description, single_use=False, persistent=True, **import_args)
            except dbus.exceptions.DBusException as excp:
                msg = excp.get_dbus_message()
                msg = re.sub(r'^.*GDBus.Error:[^\s]*', '', msg).strip()
                self.error(
                    msg=f"Failed to import configuration {name}:\n{msg}",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            except Exception as e:
                self.error(
                    msg=f"Unexpected error during configuration import:\n{str(e)}",
                    notify=False,
                    dialog=True,
                    title="Configuration Import Failed"
                )
                return
            if self.manager_version >= 22:
                try:
                    v = config_obj.Validate()
                except dbus.exceptions.DBusException as excp:
                    msg = excp.get_dbus_message()
                    msg = re.sub(r'^.*GDBus.Error:[^\s]*', '', msg).strip()
                    self.error(
                        msg=f"OpenVPN Config {name} imported from {path} failed validation:\n{msg}",
                        notify=False,
                        dialog=True,
                        title="Configuration Import Failed"
                    )
                    self.info(f'Removing Config {name}')
                    config_obj.Remove()
                    return

            self.invalid_sessions = True
            self.info(msg=f'Successfully imported config {name} from {path}', notify=True)
        except:
            self.debug(traceback.format_exc())
            self.error(
                msg=f"Unexpected error importing configuration {name} from {path}",
                notify=False,
                dialog=True,
                title="Configuration Import Failed"
            )

    def action_config_import(self, _object):
        self.info(f'Import Config')
        dialog = construct_configuration_select_dialog(on_import=self.on_config_import)
        dialog.set_visible(True)

    def action_config_open(self, path):
        self.info(f'Import Config {path}')
        dialog = construct_configuration_import_dialog(path=path, on_import=self.on_config_import)
        dialog.set_visible(True)

    def action_about(self, _object):
        self.info(f'About')
        dialog = construct_about_dialog()
        dialog.set_visible(True)

    def action_quit(self, _object):
        self.info(f'Quit')
        self.release()

    def logging_notify(self, msg, title=f'{APPLICATION_NAME}', icon='active'):
        icon = f'{APPLICATION_NAME}-{icon}'
        self.multi_notifier.new_notifier(
            identifier = 'logging',
            title = title,
            body = msg,
            icon = icon,
            active = True,
            timespan = 2,
        )
        self.multi_notifier.update()

    def debug(self, msg, notify=False, *args, **kwargs):
        logging.debug(msg, *args, **kwargs)
        if notify:
            self.logging_notify(msg)

    def info(self, msg, notify=False, dialog=False, title=None, *args, **kwargs):
        logging.info(msg, *args, **kwargs)
        if notify:
            self.logging_notify(msg)

        if dialog:
            show_info_notification(title=title, message=msg)

    def warning(self, msg, notify=False, dialog=False, title=None, *args, **kwargs):
        logging.warning(msg, *args, **kwargs)
        if notify:
            self.logging_notify(msg, icon='active-error')

        if dialog:
            show_warning_notification(title=title, message=msg)

    def error(self, msg, notify=False, dialog=False, title=None, *args, **kwargs):
        logging.error(msg, *args, **kwargs)
        if notify:
            self.logging_notify(msg, icon="active-error")

        if dialog:
            show_error_dialog(title=title, message=msg)
