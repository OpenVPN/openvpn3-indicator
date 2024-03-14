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
import time
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio

from openvpn3_indicator.about import *

###
#
# MultiNotifier
#
###

class MultiNotifier():
    @property
    def identifier(self):
        return self._identifier
    def sub_identifier(self, identifier):
        return f'{self.identifier}-{identifier}'
    @property
    def  application(self):
        return self._application

    def __init__(self, application, identifier):
        self._identifier = identifier
        self._application = application
        self._notifiers = dict()
        self._pending = list()
        self.default_icon = f'{APPLICATION_NAME}'
        self.default_title = f'{APPLICATION_TITLE}'
        self.default_body = None
        self.default_category = None
        self.default_priority = Gio.NotificationPriority.NORMAL
        self.default_timespan = None
        self.invalid = False

    def invalidate(self):
        self.invalid = True

    class Notifier():
        @property
        def parent(self):
            return self._parent
        @property
        def identifier(self):
            return self._identifier
        @property
        def sent(self):
            return self._sent
        @property
        def timeout(self):
            return self._timeout

        def __init__(self, parent, identifier, active=False, icon=None, title=None, body=None, category=None, priority=None, timespan=None):
            self._parent = parent
            self._identifier = identifier
            self._active = active
            self._icon = icon or self.parent.default_icon
            self._title = title or self.parent.default_title
            self._body = body or self.parent.default_body
            self._category = category or self.parent.default_category
            self._priority = priority or self.parent.default_priority
            self._timespan = timespan or self.parent.default_timespan
            self._sent = None
            self._timeout = None

        def close(self):
            if self.parent:
                self.parent.del_notifier(self)
        @property
        def active(self):
            return self._active
        @active.setter
        def active(self, active):
            active = bool(active)
            if self._active != active:
                self._active = active
                if not self._active:
                    if self._sent and self.parent:
                        self.parent.application.withdraw_notification(self.identifier)
                    self._sent = None
                    self._timeout = None
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
        def body(self):
            return self._body
        @body.setter
        def body(self, body):
            body = str(body)
            if self._body != body:
                self._body = body
                if self.parent and self.active:
                    self.parent.invalidate()
        @property
        def category(self):
            return self._category
        @category.setter
        def category(self, category):
            category = str(category)
            if self._category != category:
                self._category = category
                if self.parent and self.active:
                    self.parent.invalidate()
        @property
        def priority(self):
            return self._priority
        @priority.setter
        def priority(self, priority):
            if self._priority != priority:
                self._priority = priority
                if self.parent and self.active:
                    self.parent.invalidate()
        @property
        def timespan(self):
            return self._timespan
        @timespan.setter
        def timespan(self, timespan):
            if self._timespan != timespan:
                self._timespan = timespan
                if self.parent and self.active:
                    self.parent.invalidate()

    def new_notifier(self, identifier=None, **kwargs):
        identifier = self.sub_identifier(identifier or str(uuid.uuid4()))
        notifier = self.Notifier(self, identifier=identifier, **kwargs)
        self._notifiers[identifier] = notifier
        logging.debug(f'Created Notifier {identifier}')
        if notifier.active:
            self.invalidate()
        return notifier
    def del_notifier(self, notifier):
        if notifier.parent == self:
            if notifier.identifier in self._notifiers:
                if notifier.active:
                    self._pending.append(notifier)
                del self._notifiers[notifier.identifier]
                logging.debug(f'Destroyed Notifier {notifier.identifier}')
            notifier._parent = None

    def commit_notifier(self, notifier):
        if notifier.timeout is not None and notifier.timeout < time.monotonic():
            notifier.active = False
        if notifier.active and notifier.sent is None:
            notifier._sent = time.monotonic()
            notifier._timeout = notifier.timespan and notifier.sent + notifier.timespan

            target = Gio.Notification.new(notifier.title or '')
            if notifier.icon is not None:
                icon = Gio.Icon.new_for_string(notifier.icon)
                target.set_icon(icon)
            if notifier.title is not None:
                target.set_title(notifier.title)
            if notifier.body is not None:
                target.set_body(notifier.body)
            if notifier.category is not None:
                target.set_category(notifier.category)
            if notifier.priority is not None:
                target.set_priority(notifier.priority)
            self.application.send_notification(notifier.identifier, target)
        if not notifier.active and notifier.sent is not None:
            notifier._sent = None
            notifier._timeout = None
            self.application.withdraw_notification(notifier.identifier)

    def update(self):
        for notifier in self._notifiers.values():
            self.commit_notifier(notifier)
        new_pending = list()
        for notifier in self._pending:
            self.commit_notifier(notifier)
            if notifier.active:
                new_pending.append(notifier)
        self._pending = new_pending
        self.invalid = False

    def close(self):
        for notifier in list(self._notifiers.values()):
            notifier.close()
