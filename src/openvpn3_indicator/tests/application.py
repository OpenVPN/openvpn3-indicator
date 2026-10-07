#!/usr/bin/env python3

import unittest
from unittest import mock

import dbus

from openvpn3_indicator.application import Application
from openvpn3_indicator.multi_indicator import MENU_UNSET, MultiIndicator


class StatusNotifierWatcherTest(unittest.TestCase):
    def test_get_status_notifier_watcher_owner_requires_watcher_protocol(self):
        properties = mock.Mock()
        watcher = mock.Mock()
        bus = mock.Mock()
        bus.get_name_owner.return_value = ':1.42'
        bus.get_object.return_value = watcher
        application = mock.Mock(session_bus=bus)

        with mock.patch('openvpn3_indicator.application.dbus.Interface', return_value=properties):
            owner = Application.get_status_notifier_watcher_owner(application)

        self.assertEqual(':1.42', owner)
        bus.get_object.assert_called_once_with('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
        properties.Get.assert_called_once_with('org.kde.StatusNotifierWatcher', 'ProtocolVersion')

    def test_get_status_notifier_watcher_owner_rejects_owner_change(self):
        properties = mock.Mock()
        bus = mock.Mock()
        bus.get_name_owner.side_effect = [':1.42', ':1.43']
        application = mock.Mock(session_bus=bus)

        with mock.patch('openvpn3_indicator.application.dbus.Interface', return_value=properties):
            with self.assertRaises(dbus.exceptions.DBusException):
                Application.get_status_notifier_watcher_owner(application)

    def test_wait_for_status_notifier_watcher_retries_until_ready(self):
        application = mock.Mock()
        application.get_status_notifier_watcher_owner.side_effect = [
            dbus.exceptions.DBusException('not ready'),
            dbus.exceptions.DBusException('not ready'),
            ':1.42',
        ]

        with mock.patch('openvpn3_indicator.application.time.sleep') as sleep:
            ready = Application.wait_for_status_notifier_watcher(application, retries=3, delay=0.1)

        self.assertTrue(ready)
        self.assertEqual(2, sleep.call_count)

    def test_unavailable_watcher_is_retried_with_backoff(self):
        application = mock.Mock(status_notifier_watcher_refresh_generation=1)
        application.get_status_notifier_watcher_owner.side_effect = dbus.exceptions.DBusException('not ready')
        application.schedule_status_notifier_watcher_refresh.side_effect = lambda *args: Application.schedule_status_notifier_watcher_refresh(application, *args)

        with mock.patch('openvpn3_indicator.application.GLib.timeout_add') as timeout_add:
            result = Application.refresh_status_notifier_watcher(application, ':1.42', 1, 20)

        self.assertFalse(result)
        application.warning.assert_called_once()
        timeout_add.assert_called_once_with(
            5000,
            application.refresh_status_notifier_watcher,
            ':1.42',
            1,
            21,
        )

    def test_ready_watcher_republishes_after_passive_status(self):
        application = mock.Mock(status_notifier_watcher_refresh_generation=1)
        application.get_status_notifier_watcher_owner.return_value = ':1.42'

        with mock.patch('openvpn3_indicator.application.GLib.timeout_add') as timeout_add:
            result = Application.refresh_status_notifier_watcher(application, ':1.42', 1, 0)

        self.assertFalse(result)
        application.multi_indicator.reset.assert_called_once_with()
        application.multi_indicator.update.assert_not_called()
        timeout_add.assert_called_once_with(
            100,
            application.republish_status_notifier_watcher,
            1,
        )

    def test_indicator_replaces_menu_only_when_its_key_changes(self):
        parent = mock.Mock()
        parent.default_icon = 'icon'
        parent.default_description = 'description'
        parent.default_title = 'title'
        indicator = MultiIndicator.Indicator(parent, 'test')
        first_menu = object()

        self.assertTrue(indicator.set_menu(('idle',), first_menu))
        self.assertFalse(indicator.set_menu(('idle',), object()))
        self.assertIs(first_menu, indicator.menu)
        self.assertTrue(indicator.set_menu(('connected',), object()))

    def test_committing_an_icon_change_does_not_reset_the_menu(self):
        multi_indicator = MultiIndicator.__new__(MultiIndicator)
        multi_indicator._sub_menu_keys = [MENU_UNSET]
        target = mock.Mock()
        multi_indicator.sub_indicator = lambda num: target
        indicator = mock.Mock(
            icon='icon',
            description='description',
            title='title',
            menu=object(),
            menu_key=('idle',),
        )

        MultiIndicator.commit_indicator(multi_indicator, indicator, 0)
        MultiIndicator.commit_indicator(multi_indicator, indicator, 0)

        target.set_menu.assert_called_once_with(indicator.menu)
        indicator.menu_key = ('connected',)
        MultiIndicator.commit_indicator(multi_indicator, indicator, 0)
        self.assertEqual(2, target.set_menu.call_count)

    def test_first_commit_configures_an_empty_menu(self):
        multi_indicator = MultiIndicator.__new__(MultiIndicator)
        multi_indicator._sub_menu_keys = [MENU_UNSET]
        target = mock.Mock()
        multi_indicator.sub_indicator = lambda num: target
        indicator = mock.Mock(
            icon='icon',
            description='description',
            title='title',
            menu=None,
            menu_key=None,
        )

        with mock.patch('openvpn3_indicator.multi_indicator.Gtk.Menu') as menu:
            MultiIndicator.commit_indicator(multi_indicator, indicator, 0)

        target.set_menu.assert_called_once_with(menu.return_value)


if __name__ == '__main__':
    unittest.main()
