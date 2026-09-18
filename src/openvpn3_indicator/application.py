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

import functools
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
from openvpn3_indicator.check_menu_item import StateCheckMenuItem
from openvpn3_indicator.credential_store import CredentialStore
from openvpn3_indicator.dialogs.about import construct_about_dialog
from openvpn3_indicator.dialogs.system_checks import construct_appindicator_missing_dialog
from openvpn3_indicator.dialogs.credentials import CredentialsUserInput, construct_credentials_dialog
from openvpn3_indicator.dialogs.configuration import construct_configuration_select_dialog, construct_configuration_import_dialog, construct_configuration_remove_dialog
from openvpn3_indicator.dialogs.notification import show_error_dialog, show_warning_notification, show_info_notification
from openvpn3_indicator.status import get_status_icon, get_status_description, get_status_class, get_status_marker, get_aggregate_icon


#TODO: Which input slots should not be stored ? (OTPs, etc.)
#TODO: Understand better the possible session state changes
#TODO: Collect and present session logs and stats
#TODO: Implement other than AppIndicator ways to have system tray icon
#TODO: /usr/share/metainfo ?
#TODO: Understand mimetype icons inheritance
#TODO: Prepare localization

DEFAULT_CONFIG_NAME = gettext.gettext('UNKNOWN')
DEFAULT_SESSION_NAME = gettext.gettext('UNKNOWN')

# Values of the indicator-mode setting.
INDICATOR_MODE_SINGLE = 'single'
INDICATOR_MODE_PER_SESSION = 'per-session'
INDICATOR_MODES = (INDICATOR_MODE_SINGLE, INDICATOR_MODE_PER_SESSION)

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
        self.clear_secret_storage = False
        self.add_main_option('clear-secret-storage', ord('c'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Remove all data stored in secret storage", None)
        self.add_main_option('repair', ord('r'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, "Ask the running instance to re-create its tray icons and exit", None)
        repair_action = Gio.SimpleAction.new('repair', None)
        repair_action.connect('activate', self.on_action_repair)
        self.add_action(repair_action)
        self.connect('handle-local-options', self.on_handle_local_options)
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.connect('open', self.on_open)
        self.connect('shutdown', self.on_shutdown)

    def on_handle_local_options(self, application, options):
        options = options.end().unpack()
        level=logging.WARNING
        if options.get('version', False):
            print(f'{APPLICATION_NAME} {APPLICATION_VERSION}')
            return 0
        if options.get('clear-secret-storage', False):
            self.clear_secret_storage = True
        if options.get('debug', False):
            level = logging.DEBUG
        elif options.get('silent', False):
            level = logging.INFO
        elif options.get('verbose', False):
            level = logging.ERROR
        logging.basicConfig(level = level)
        if options.get('repair', False):
            # Forward the request to the running instance through the exported
            # action group.  If no instance is running this process becomes
            # the primary one and simply starts up; there is nothing to repair
            # yet in that case.
            try:
                self.register(None)
            except GLib.Error as excp:
                logging.critical(f'Failed to register application: {excp.message}')
                return 1
            if self.get_is_remote():
                self.activate_action('repair', None)
                # The remote activation is sent asynchronously; make sure it
                # has left this process before we exit.
                try:
                    self.get_dbus_connection().flush_sync(None)
                except GLib.Error as excp:
                    logging.warning(f'Failed to flush D-Bus connection: {excp.message}')
                return 0
        return -1

    def on_activate(self, data):
        self.info(f'Activate')
        if self.startup_activation_pending:
            # First activation of the primary instance, emitted by
            # Gtk.Application right after startup.
            self.startup_activation_pending = False
            return
        # Emitted on the running instance when the user launches the
        # application again.  The only reason to do that is a missing tray
        # icon, so treat it as a repair request.
        self.repair_indicators()

    def on_action_repair(self, action, parameter):
        self.info(f'Repair requested')
        self.repair_indicators()

    def on_startup_activation_done(self):
        # Runs on the first main loop iteration, after the startup activation.
        self.startup_activation_pending = False
        return GLib.SOURCE_REMOVE

    def repair_indicators(self):
        # Manual repair for a tray icon that went missing for whatever reason:
        # re-create the indicator objects under fresh ids so the status host
        # has to build new items from scratch.
        if not hasattr(self, 'multi_indicator'):
            return
        if not self.schedule_alive():
            self.warning('Scheduler was not running, restarting it')
            self.schedule_source = GLib.timeout_add(1000, self.on_schedule)
        try:
            self.session_bus.get_name_owner('org.kde.StatusNotifierWatcher')
        except dbus.exceptions.DBusException:
            self.error('No system tray found on the session bus. Please enable the AppIndicator extension of your desktop.', notify=True)
            return
        self.multi_indicator.recreate()
        self.last_ui_signature = None
        self.invalid_ui = True
        self.refresh_ui()
        self.info('Tray icons re-created', notify=True)

    def verify_registration(self):
        # Every slot that should be visible must be listed by the watcher;
        # libappindicator does not retry a failed registration by itself.
        try:
            watcher = self.session_bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
            properties = dbus.Interface(watcher, dbus_interface='org.freedesktop.DBus.Properties')
            registered = properties.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems', timeout=5)
        except dbus.exceptions.DBusException as excp:
            self.debug(f'Cannot read the registered items of the StatusNotifierWatcher: {excp}')
            return
        # libappindicator exports the items on the shared GDBus session
        # connection, which has a different unique name than dbus-python's
        # self.session_bus.
        connection = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.multi_indicator.verify_registration(str(connection.get_unique_name()), registered)

    def schedule_alive(self):
        source_id = getattr(self, 'schedule_source', 0)
        if not source_id:
            return False
        source = GLib.MainContext.default().find_source_by_id(source_id)
        return source is not None and not source.is_destroyed()

    def on_open(self, application, files, n_files, hint):
        self.info(f'Open {n_files} {hint}')
        for file in files:
            config_path = file.get_path()
            self.action_config_open(config_path)

    def on_shutdown(self, application):
        self.info('Shutdown')
        if hasattr(self, 'multi_indicator'):
            self.multi_indicator.close()
        if hasattr(self, 'multi_notifier'):
            self.multi_notifier.close()

    def on_startup(self, data):
        self.info(f'Startup')
        self.startup_activation_pending = True
        GLib.idle_add(self.on_startup_activation_done)
        DBusGMainLoop(set_as_default=True)

        bus = dbus.Bus()
        self.session_bus = bus
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
        self.session_bus.add_signal_receiver(
            self.on_status_notifier_watcher_owner_changed,
            signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',
            bus_name='org.freedesktop.DBus',
            arg0='org.kde.StatusNotifierWatcher',
        )

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
        if self.clear_secret_storage:
            for config in self.credential_store.keys():
                credentials = self.credential_store[config]
                for key in list(credentials.keys()):
                    self.info(f'Removing entry {key} from secret storage')
                    del credentials[key]

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
        # Logical indicators currently shown, keyed by session id, or by None
        # for the indicator that represents the application as a whole.
        self.indicators = dict()
        self.last_ui_signature = None
        self.settings.connect('changed::indicator-mode', self.on_settings_indicator_mode_changed)
        self.info(f'Indicator mode: {self.indicator_mode}')

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

        self.schedule_source = GLib.timeout_add(1000, self.on_schedule)
        self.hold()

    def on_status_notifier_watcher_owner_changed(self, name, old_owner, new_owner):
        old_owner = str(old_owner)
        new_owner = str(new_owner)
        self.info(f'StatusNotifierWatcher owner changed from {old_owner or "<none>"} to {new_owner or "<none>"}')
        if not new_owner:
            return
        # libappindicator watches this name itself and re-registers every
        # indicator with the new watcher.  Do not recreate the indicator
        # objects here: the old objects stay alive until the watcher replies,
        # so new objects with the same ids could not export their D-Bus paths
        # ("An object is already exported"), and a Passive status sent while
        # the shell is still setting up its proxy makes the icon disappear
        # for good.  Only retry a registration that may have failed while the
        # watcher was still starting, and do it before the GNOME extension's
        # 2 s "brute-force" scan registers the same object under a different
        # id (upstream issue #38).
        for delay_ms in (1000, 4000):
            GLib.timeout_add(delay_ms, self.on_watcher_poke)

    def on_watcher_poke(self):
        if hasattr(self, 'multi_indicator'):
            self.multi_indicator.poke_registration()
        return GLib.SOURCE_REMOVE

    def settings_has_key(self, key):
        schema = self.settings.get_property('settings-schema')
        return schema is not None and schema.has_key(key)

    @property
    def indicator_mode(self):
        # Tolerate an older installed schema without the key.
        if self.settings_has_key('indicator-mode'):
            mode = self.settings.get_string('indicator-mode')
            if mode in INDICATOR_MODES:
                return mode
        return INDICATOR_MODE_SINGLE

    def on_settings_indicator_mode_changed(self, settings, key):
        self.info(f'Indicator mode changed to {self.indicator_mode}')
        self.invalid_ui = True
        self.refresh_ui()

    def plan_indicators(self):
        # Describe the tray icons wanted for the current sessions and mode.
        # Each entry: key (session id, or None for the application icon),
        # icon, title, description, order key and a menu builder.
        plans = list()
        if self.indicator_mode == INDICATOR_MODE_PER_SESSION and len(self.sessions) > 0:
            for session_id in self.sessions:
                session_name = self.get_session_name(session_id)
                plans.append({
                    'key': session_id,
                    'icon': self.session_icon(session_id),
                    'title': f'{APPLICATION_TITLE}: {session_name}',
                    'description': f'{APPLICATION_TITLE}: {session_name}',
                    'order_key': f'1-{session_name}-{session_id}',
                    'menu': functools.partial(self.construct_session_menu, session_id),
                })
        else:
            if self.indicator_mode == INDICATOR_MODE_SINGLE:
                title = f'{APPLICATION_TITLE}: {self.sessions_summary()}'
            else:
                title = f'{APPLICATION_TITLE}'
            plans.append({
                'key': None,
                'icon': self.aggregate_icon(),
                'title': title,
                'description': title,
                'order_key': '0',
                'menu': self.construct_main_menu,
            })
        return plans

    def ui_signature(self):
        # Everything the indicators and their menus are built from.  While it
        # is unchanged the existing Gtk.Menu objects are kept: a new menu
        # closes the menu the user may have open and makes hosts refresh the
        # icon.
        return (
            self.indicator_mode,
            self.settings.get_string('startup-action'),
            tuple(sorted(self.sessions)),
            tuple(sorted(self.config_names.items())),
            tuple(sorted((config_id, tuple(session_ids)) for config_id, session_ids in self.config_sessions.items())),
            tuple(sorted(self.session_configs.items())),
            tuple(sorted((session_id, status['major'], status['minor']) for session_id, status in self.session_statuses.items() if session_id in self.sessions)),
        )

    def refresh_ui(self):
        if not self.invalid_ui:
            return
        signature = self.ui_signature()
        rebuild_menus = signature != self.last_ui_signature
        new_indicators = dict()
        for plan in self.plan_indicators():
            indicator = self.indicators.get(plan['key'], None)
            if indicator is None:
                indicator = self.multi_indicator.new_indicator()
            indicator.icon = plan['icon']
            indicator.description = plan['description']
            indicator.title = plan['title']
            indicator.order_key = plan['order_key']
            if rebuild_menus or indicator.menu is None:
                indicator.menu = plan['menu']()
            indicator.active = True
            new_indicators[plan['key']] = indicator
        self.last_ui_signature = signature
        for key, indicator in self.indicators.items():
            if key not in new_indicators:
                indicator.close()
        self.indicators = new_indicators

        new_notifiers = dict()
        for session_id in self.sessions:
            notifier = self.notifiers.get(session_id, None)
            if notifier is None:
                session_name = self.get_session_name(session_id)
                notifier = self.multi_notifier.new_notifier(f'session-{session_id}-status', mute_repetitions=True)
                notifier.icon = self.session_icon(session_id)
                notifier.title = f'{APPLICATION_TITLE}: {session_name}'
                notifier.body = self.session_description(session_id)
                notifier.active = False
            new_notifiers[session_id] = notifier
        for session_id, notifier in self.notifiers.items():
            if session_id not in new_notifiers:
                notifier.close()
        self.notifiers = new_notifiers

        self.multi_indicator.update()
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
                def status_keys(statuses):
                    return dict([ (session_id, (status['major'], status['minor'])) for session_id, status in statuses.items() ])
                changed = (
                    set(new_sessions) != set(self.sessions)
                    or new_config_names != self.config_names
                    or new_config_sessions != self.config_sessions
                    or new_session_configs != self.session_configs
                    or status_keys(new_session_statuses) != status_keys(self.session_statuses)
                )
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
                if changed:
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
        # Check items: the status host draws the mark of the selected entry
        # in the menu's left border (dbusmenu toggle-type "checkmark").  The
        # mark follows the setting only, see StateCheckMenuItem.
        choices = [
            ('', gettext.gettext('No Connection')),
            ('RESTART', gettext.gettext('Restart Connection')),
        ]
        for config_name, config_id in sorted(self.name_configs.items()):
            choices.append((f'STARTNAME:{config_name}', gettext.gettext('Start {name}').format(name=config_name)))
        for menu_action, menu_title in choices:
            menu_item = StateCheckMenuItem(menu_title, active=(startup_action == menu_action))
            menu_item.connect('activate', self.action_settings_startup, menu_action)
            menu.append(menu_item)
        return menu

    def construct_menu_settings_indicator(self):
        current_mode = self.indicator_mode
        menu = Gtk.Menu()
        for mode, menu_title in (
                (INDICATOR_MODE_SINGLE, gettext.gettext('Single Icon')),
                (INDICATOR_MODE_PER_SESSION, gettext.gettext('One Icon per Connection')),
            ):
            menu_item = StateCheckMenuItem(menu_title, active=(current_mode == mode))
            menu_item.connect('activate', self.action_settings_indicator_mode, mode)
            menu.append(menu_item)
        return menu

    def action_settings_indicator_mode(self, _object, mode):
        self.info(f'Set indicator mode {mode}')
        if not self.settings_has_key('indicator-mode'):
            self.warning('The installed settings schema has no indicator-mode key. Please reinstall the application.', notify=True)
            return
        self.settings.set_string('indicator-mode', mode)
        self.invalid_ui = True
        self.refresh_ui()

    def construct_menu_config(self, config_id):
        menu = Gtk.Menu()
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Connect'))
        menu_item.connect('activate', self.action_config_connect, config_id)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Remove'))
        menu_item.connect('activate', self.action_config_remove, config_id)
        menu.append(menu_item)
        return menu

    def construct_menu_session(self, session_id, header=None):
        # Operations on one session.  Without a header the session name is
        # shown on top (the per-session icon menu); with a header, for
        # example the status text, that header is shown as an inactive item.
        menu = Gtk.Menu()
        status = self.session_statuses.get(session_id, None)
        major = status['major'] if status else None
        minor = status['minor'] if status else None
        if header is None:
            menu_item = Gtk.MenuItem.new_with_label(self.get_session_name(session_id))
        else:
            menu_item = Gtk.MenuItem.new_with_label(header)
            menu_item.set_sensitive(False)
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

    def construct_menu_item_session(self, label, session_id):
        # Submenu entry for a running session: a check item that is checked
        # while the session is connected (drawn in the menu's left border by
        # the status host), a text marker for the transient states, the
        # status text on top of the submenu and the session operations below.
        marker = self.session_marker(session_id)
        if marker:
            label = f'{label} {marker}'
        menu_item = StateCheckMenuItem(label, active=self.session_connected(session_id))
        menu_item.set_submenu(self.construct_menu_session(session_id, header=self.session_description(session_id)))
        return menu_item

    def session_connected(self, session_id):
        status = self.session_statuses.get(session_id, None)
        if status is None:
            return False
        return get_status_class(status['major'], status['minor']) == 'active'

    def construct_menu_configurations(self, menu, include_sessions):
        # Append one submenu per configuration, sorted by name.  Configurations
        # without a session get Connect and Remove.  Configurations with a
        # session are listed with their session operations when
        # include_sessions is set, otherwise skipped (the per-session icon
        # menus show only the idle configurations).  Returns whether anything
        # was appended.
        added = False
        listed_sessions = set()
        for config_name, config_id in sorted(self.name_configs.items()):
            session_ids = [ session_id for session_id in self.config_sessions.get(config_id, [])
                            if session_id in self.sessions ]
            if len(session_ids) == 0:
                menu_item = Gtk.MenuItem.new_with_label(config_name)
                menu_item.set_submenu(self.construct_menu_config(config_id))
                menu.append(menu_item)
                added = True
            elif include_sessions:
                for number, session_id in enumerate(session_ids, start=1):
                    label = config_name
                    if len(session_ids) > 1:
                        label = f'{label} #{number}'
                    menu.append(self.construct_menu_item_session(label, session_id))
                    listed_sessions.add(session_id)
                    added = True
        if include_sessions:
            # Sessions whose configuration is not (or no longer) known.
            for session_id in self.sessions:
                if session_id not in listed_sessions:
                    menu.append(self.construct_menu_item_session(self.get_session_name(session_id), session_id))
                    added = True
        return added

    def construct_menu_tail(self, menu):
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Import Config'))
        menu_item.connect('activate', self.action_config_import)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Startup Settings'))
        menu_item.set_submenu(self.construct_menu_settings_startup())
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Tray Icon Settings'))
        menu_item.set_submenu(self.construct_menu_settings_indicator())
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('About'))
        menu_item.connect('activate', self.action_about)
        menu.append(menu_item)
        menu_item = Gtk.MenuItem.new_with_label(gettext.gettext('Quit'))
        menu_item.connect('activate', self.action_quit)
        menu.append(menu_item)
        menu.show_all()
        return menu

    def construct_session_menu(self, session_id):
        # Menu of a per-session icon: this session's operations, then the idle
        # configurations, then the common items.
        menu = self.construct_menu_session(session_id)
        menu.append(Gtk.SeparatorMenuItem())
        if self.construct_menu_configurations(menu, include_sessions=False):
            menu.append(Gtk.SeparatorMenuItem())
        return self.construct_menu_tail(menu)

    def construct_main_menu(self):
        # Menu of the single icon (and of the idle icon in per-session mode):
        # every configuration as a submenu, then the common items.
        menu = Gtk.Menu()
        if self.construct_menu_configurations(menu, include_sessions=True):
            menu.append(Gtk.SeparatorMenuItem())
        return self.construct_menu_tail(menu)

    def session_marker(self, session_id):
        status = self.session_statuses.get(session_id, None)
        if status is None:
            return ''
        return get_status_marker(status['major'], status['minor'])

    def aggregate_icon(self):
        statuses = [ (status['major'], status['minor'])
                     for session_id, status in self.session_statuses.items()
                     if session_id in self.sessions ]
        return get_aggregate_icon(statuses)

    def sessions_summary(self):
        parts = list()
        for session_id in sorted(self.sessions, key=lambda session_id: (self.get_session_name(session_id), session_id)):
            parts.append(f'{self.get_session_name(session_id)}: {self.session_description(session_id)}')
        if len(parts) == 0:
            return gettext.gettext('No active connection')
        return ', '.join(parts)

    def session_icon(self, session_id):
        status = self.session_statuses.get(session_id, None)
        if status is None:
            return get_status_icon(None, None)
        return get_status_icon(status['major'], status['minor'])

    def session_description(self, session_id):
        status = self.session_statuses.get(session_id, None)
        if status is None:
            return get_status_description(None, None)
        return get_status_description(status['major'], status['minor'])

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
        if session_id not in self.sessions:
            return
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
                    store_credentials = dict([ (ui.name, ui.value) for ui in user_inputs if ui.can_store and ui.value ])
                    self.store_set_credentials(config_id, store_credentials)
                else:
                    self.store_clear_credentials(config_id, credentials.keys())
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
                self.on_session_credentials(session_id, credentials)

            session_name = self.get_session_name(session_id)
            def remain_active():
                self.debug('Remain active')
                if session_id in self.session_statuses:
                    major = self.session_statuses[session_id]['major']
                    minor = self.session_statuses[session_id]['minor']
                    if openvpn3.StatusMajor.CONNECTION == major and openvpn3.StatusMinor.CFG_REQUIRE_USER == minor:
                        return True
                if session_id in self.session_dialogs:
                    del self.session_dialogs[session_id]
                return False
            dialog = construct_credentials_dialog(session_name, user_inputs, on_connect=on_connect, on_cancel=on_cancel, remain_active=remain_active)
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
        # Repeating GLib source.  An exception escaping from here would remove
        # the source and freeze the whole application, so catch everything.
        try:
            self.debug(f'Schedule')
            if self.last_invalid + 30 < time.monotonic():
                self.debug('Forced refresh of sessions')
                self.invalid_sessions = True
                self.verify_registration()
            if self.invalid_sessions:
                self.last_invalid = time.monotonic()
                self.refresh_sessions()
            if self.invalid_ui:
                self.refresh_ui()
            self.multi_notifier.update()
            if self.startup_config_id or self.startup_config_name:
                config_id = self.startup_config_id or self.name_configs.get(self.startup_config_name, None)
                if config_id and len(self.config_sessions.get(config_id, [])) == 0:
                    self.debug(f'Starting config {config_id} as requested in startup settings.')
                    self.action_config_connect(None, config_id)
                self.startup_config_id = None
                self.startup_config_name = None
        except Exception:
            self.debug(traceback.format_exc())
            self.warning('Scheduled refresh failed')
        return GLib.SOURCE_CONTINUE

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
            mute_repetitions = False,
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
