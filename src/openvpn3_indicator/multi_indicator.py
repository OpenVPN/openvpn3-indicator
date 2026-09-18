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

import logging
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3

from openvpn3_indicator.about import *

###
#
# MultiIndicator
#
###

class MultiIndicator():

    # Delay between reconnecting to a StatusNotifierWatcher and re-announcing
    # the status of the visible indicators.  The GNOME AppIndicator extension
    # creates a fresh D-Bus proxy for every (re)registered item and GDBusProxy
    # drops signals until that proxy has loaded its properties, so a NewStatus
    # sent right after the registration may never be seen by the shell.
    REASSERT_DELAY_MS = 1500

    @property
    def identifier(self):
        return self._identifier

    def sub_identifier(self, num):
        # After a recreate() the ids carry a generation marker, so that the
        # new objects get D-Bus paths that never collide with the old ones.
        identifier = self.identifier
        if self._generation > 0:
            identifier = f'{identifier}-r{self._generation}'
        if num == 0:
            return identifier
        return f'{identifier}-{num}'

    def sub_indicator(self, num):
        while len(self._sub_indicators) <= num:
            index = len(self._sub_indicators)
            sub = AppIndicator3.Indicator.new(
                self.sub_identifier(index),
                self.default_icon,
                self.default_category
                )
            sub.set_ordering_index(index)
            handler = sub.connect('connection-changed', self.on_sub_connection_changed, index)
            self._sub_indicators.append(sub)
            self._sub_handlers.append(handler)
            self._sub_connected.append(None)
            self._reassert_sources.append(0)
            self._sub_menus.append(None)
        return self._sub_indicators[num]

    def __init__(self, identifier):
        self._identifier = identifier
        self._generation = 0
        self._sub_indicators = list()
        # Per slot: handler id of the connection-changed signal.
        self._sub_handlers = list()
        # Per slot: None = never registered with a StatusNotifierWatcher,
        # True/False = currently registered or not.
        self._sub_connected = list()
        # Per slot: GLib source id of a pending status re-assert, or 0.
        self._reassert_sources = list()
        # Per slot: the Gtk.Menu currently set on the AppIndicator.
        self._sub_menus = list()
        self._empty_menu = None
        self._indicators = dict()
        self.default_icon = f'{APPLICATION_NAME}'
        self.default_description = f'{APPLICATION_TITLE}'
        self.default_title = f'{APPLICATION_TITLE}'
        self.default_category = AppIndicator3.IndicatorCategory.SYSTEM_SERVICES
        self.invalid = False

    def invalidate(self):
        self.invalid = True

    class Indicator():

        @property
        def parent(self):
            return self._parent

        @property
        def identifier(self):
            return self._identifier

        def __init__(self, parent, identifier, active=False, icon=None, description=None, title=None, order_key=None, menu=None):
            self._parent = parent
            self._identifier = identifier
            self._active = active
            self._icon = icon or self.parent.default_icon
            self._description = description or self.parent.default_description
            self._title = title or self.parent.default_title
            self._order_key = order_key or self.identifier
            self._menu = menu

        def close(self):
            if self.parent:
                self.parent.del_indicator(self)

        @property
        def active(self):
            return self._active
        @active.setter
        def active(self, active):
            active = bool(active)
            if self._active != active:
                self._active = active
                if self.parent:
                    self.parent.invalidate()

        @property
        def icon(self):
            return self._icon
        @icon.setter
        def icon(self, icon):
            icon = str(icon)
            if self._icon != icon:
                self._icon = icon
                if self.parent and self.active:
                    self.parent.invalidate()

        @property
        def description(self):
            return self._description
        @description.setter
        def description(self, description):
            description = str(description)
            if self._description != description:
                self._description = description
                if self.parent and self.active:
                    self.parent.invalidate()

        @property
        def title(self):
            return self._title
        @title.setter
        def title(self, title):
            title = str(title)
            if self._title != title:
                self._title = title
                if self.parent and self.active:
                    self.parent.invalidate()

        @property
        def order_key(self):
            return self._order_key
        @order_key.setter
        def order_key(self, order_key):
            order_key = str(order_key)
            if self._order_key != order_key:
                self._order_key = order_key
                if self.parent and self.active:
                    self.parent.invalidate()

        @property
        def menu(self):
            return self._menu
        @menu.setter
        def menu(self, menu):
            if self._menu != menu:
                self._menu = menu
                if self.parent and self.active:
                    self.parent.invalidate()

    def new_indicator(self, **kwargs):
        identifier = str(uuid.uuid4())
        indicator = self.Indicator(self, identifier, **kwargs)
        self._indicators[identifier] = indicator
        logging.debug(f'Created Indicator {identifier}')
        if indicator.active:
            self.invalidate()
        return indicator

    def del_indicator(self, indicator):
        if indicator.parent == self:
            if indicator.identifier in self._indicators:
                del self._indicators[indicator.identifier]
                if indicator.active:
                    self.invalidate()
                logging.debug(f'Destroyed Indicator {indicator.identifier}')
            indicator._parent = None

    def set_sub_menu(self, num, menu):
        # Setting a menu makes libappindicator re-parse it, which closes the
        # menu if the host has it open, and re-register the item with the
        # watcher, which makes hosts refresh the icon.  Only do it when the
        # menu really changed.
        if menu is None:
            if self._empty_menu is None:
                self._empty_menu = Gtk.Menu()
            menu = self._empty_menu
        if self._sub_menus[num] is menu:
            return
        self.sub_indicator(num).set_menu(menu)
        self._sub_menus[num] = menu

    def commit_indicator(self, indicator, num):
        target = self.sub_indicator(num)
        # set_icon_full(), set_title() and set_status() only emit when the
        # value changes.
        target.set_icon_full(indicator.icon, indicator.description)
        target.set_title(indicator.title)
        self.set_sub_menu(num, indicator.menu)
        target.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    def hide_indicator(self, num):
        target = self.sub_indicator(num)
        self.set_sub_menu(num, None)
        target.set_status(AppIndicator3.IndicatorStatus.PASSIVE)

    def on_sub_connection_changed(self, sub, connected, index):
        # Emitted by libappindicator with False when the StatusNotifierWatcher
        # disappears from the bus and with True after every successful
        # RegisterStatusNotifierItem call (also the periodic ones caused by
        # set_menu()).  Only a real reconnection is interesting here.
        connected = bool(connected)
        was_connected = self._sub_connected[index]
        self._sub_connected[index] = connected
        if not connected:
            logging.debug(f'Indicator slot {index} lost its StatusNotifierWatcher')
            self._cancel_reassert(index)
        elif was_connected is False:
            logging.debug(f'Indicator slot {index} reconnected to a StatusNotifierWatcher')
            self._schedule_reassert(index)
        elif was_connected is None:
            logging.debug(f'Indicator slot {index} registered with a StatusNotifierWatcher')

    def _schedule_reassert(self, index, delay_ms=None):
        self._cancel_reassert(index)
        if delay_ms is None:
            delay_ms = self.REASSERT_DELAY_MS
        self._reassert_sources[index] = GLib.timeout_add(delay_ms, self._on_reassert_timeout, index)

    def _cancel_reassert(self, index):
        source = self._reassert_sources[index]
        if source:
            GLib.source_remove(source)
            self._reassert_sources[index] = 0

    def _on_reassert_timeout(self, index):
        self._reassert_sources[index] = 0
        self.reassert_sub(index)
        return GLib.SOURCE_REMOVE

    def reassert_sub(self, index):
        # libappindicator only sends NewStatus when the status changes, so a
        # Passive/Active round trip is the only way to make a status host
        # re-read a status it may have cached wrongly.
        if index >= len(self._sub_indicators):
            return
        sub = self._sub_indicators[index]
        if sub.get_status() != AppIndicator3.IndicatorStatus.ACTIVE:
            return
        logging.debug(f'Re-asserting status of indicator slot {index}')
        sub.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
        sub.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    def reassert(self, delay_ms=None):
        for index in range(len(self._sub_indicators)):
            self._schedule_reassert(index, delay_ms)

    def poke_registration(self, index=None):
        # Setting icon-name to its current value changes nothing visible but
        # makes libappindicator run its watcher connection check again, which
        # exports the object if needed and re-sends RegisterStatusNotifierItem.
        # libappindicator itself never retries a failed registration.
        indices = range(len(self._sub_indicators)) if index is None else [index]
        for index in indices:
            sub = self._sub_indicators[index]
            logging.debug(f'Poking registration of indicator slot {index}')
            sub.set_property('icon-name', sub.get_property('icon-name'))

    def object_path(self, index):
        # Path under which libappindicator exports slot index (it replaces
        # every non-alphanumeric character of the id with an underscore).
        clean_id = ''.join(c if c.isalnum() else '_' for c in self.sub_identifier(index))
        return f'/org/ayatana/NotificationItem/{clean_id}'

    def verify_registration(self, bus_unique_name, registered_items):
        # registered_items: the watcher's RegisteredStatusNotifierItems.  Hosts
        # format the entries differently (GNOME: "name@path", KDE: "namepath"),
        # so just look for our bus name together with the object path.  Poke
        # the slots that should be visible but are not registered.
        registered_items = [ str(item) for item in registered_items ]
        for index, sub in enumerate(self._sub_indicators):
            if sub.get_status() != AppIndicator3.IndicatorStatus.ACTIVE:
                continue
            path = self.object_path(index)
            if any(bus_unique_name in item and path in item for item in registered_items):
                continue
            logging.warning(f'Indicator slot {index} is not registered with the StatusNotifierWatcher, retrying')
            self.poke_registration(index)

    def repair(self):
        logging.info('Repairing indicators')
        self.poke_registration()
        self.reassert()

    @property
    def generation(self):
        return self._generation

    def recreate(self):
        # Drop every AppIndicator object and build new ones with fresh ids on
        # the next update().  New ids mean new D-Bus object paths, so nothing
        # collides with old objects that libappindicator may still hold while
        # a registration is in flight, and a status host has no stale state
        # for the new items.  The old objects are announced Passive so hosts
        # hide them right away; they are released as soon as libappindicator
        # is done with them.
        self._generation += 1
        logging.info(f'Recreating indicators (generation {self._generation})')
        for index, sub in enumerate(self._sub_indicators):
            self._cancel_reassert(index)
            sub.disconnect(self._sub_handlers[index])
            sub.set_status(AppIndicator3.IndicatorStatus.PASSIVE)
        self._sub_indicators = list()
        self._sub_handlers = list()
        self._sub_connected = list()
        self._reassert_sources = list()
        self._sub_menus = list()
        self.invalid = True

    def update(self):
        if self.invalid:
            logging.debug('Repairing Indicators')
            indicators = list()
            for indicator in self._indicators.values():
                if indicator.active:
                    indicators.append(indicator)
            num = 0
            for indicator in sorted(indicators, key=lambda i : i.order_key):
                self.commit_indicator(indicator, num)
                num += 1
            for other in range(num, len(self._sub_indicators)):
                self.hide_indicator(other)
            self.invalid=False

    def close(self):
        for index in range(len(self._sub_indicators)):
            self._cancel_reassert(index)
        for indicator in list(self._indicators.values()):
            indicator.close()
