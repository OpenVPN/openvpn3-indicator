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
from gi.repository import Gtk
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

    @property
    def identifier(self):
        return self._identifier

    def sub_identifier(self, num):
        if num == 0:
            return f'{self.identifier}'
        return f'{self.identifier}-{num}'

    def sub_indicator(self, num):
        while len(self._sub_indicators) <= num:
            sub = AppIndicator3.Indicator.new(
                self.sub_identifier(len(self._sub_indicators)),
                self.default_icon,
                self.default_category
                )
            sub.set_ordering_index(num)
            self._sub_indicators.append(sub)
        return self._sub_indicators[num]

    def __init__(self, identifier):
        self._identifier = identifier
        self._sub_indicators = list()
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

    def commit_indicator(self, indicator, num):
        target = self.sub_indicator(num)
        target.set_icon_full(indicator.icon, indicator.description)
        target.set_title(indicator.title)
        if indicator.menu:
            target.set_menu(indicator.menu)
        else:
            target.set_menu(Gtk.Menu())
        target.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

    def hide_indicator(self, num):
        target = self.sub_indicator(num)
        target.set_status(AppIndicator3.IndicatorStatus.PASSIVE)

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
        for indicator in list(self._indicators.values()):
            indicator.close()
