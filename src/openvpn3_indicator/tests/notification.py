#!/usr/bin/env python3
# vim:ts=4:sts=4:sw=4:expandtab

import logging
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from openvpn3_indicator.about import APPLICATION_ID
from openvpn3_indicator.dialogs.notification import (
    show_info_notification,
    show_warning_notification,
    show_error_notification,
    show_question_notification,
    construct_notification_dialog
)

class Test(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self,
            application_id=APPLICATION_ID,
            )
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.test_step = 0

    def on_activate(self, *args, **kwargs):
        pass

    def on_startup(self, *args, **kwargs):
        self.hold()
        self.run_next_test()

    def run_next_test(self):
        if self.test_step == 0:
            print("Testing INFO notification...")
            show_info_notification(
                title="Test Info",
                message="This is an info notification test"
            )
        elif self.test_step == 1:
            print("Testing WARNING notification...")
            show_warning_notification(
                title="Test Warning",
                message="This is a warning notification test"
            )
        elif self.test_step == 2:
            print("Testing ERROR notification...")
            show_error_notification(
                title="Test Error",
                message="This is an error notification test"
            )
        elif self.test_step == 3:
            print("Testing QUESTION notification...")
            response = show_question_notification(
                title="Test Question",
                message="This is a question notification test. Do you want to continue?"
            )
            print(f"Question response: {response}")
        elif self.test_step == 4:
            print("Testing construct_notification_dialog...")
            dialog = construct_notification_dialog(
                title="Test Custom Dialog",
                message="This is a custom notification dialog test",
                message_type=Gtk.MessageType.INFO
            )
            dialog.connect('response', self.on_dialog_response)
            dialog.show()
            return
        else:
            print("All tests completed!")
            self.action_quit()
            return

        self.test_step += 1
        GLib.timeout_add(500, self.run_next_test)

    def on_dialog_response(self, dialog, response_id):
        print(f"Custom dialog response: {response_id}")
        dialog.destroy()
        self.test_step += 1
        GLib.timeout_add(500, self.run_next_test)

    def action_quit(self, *args, **kwargs):
        print("Test completed successfully!")
        self.release()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    print("Starting notification dialog tests...")
    print("Each dialog will appear sequentially. Click OK to proceed to the next test.")
    test = Test()
    test.run(sys.argv)
