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
import sys
import traceback

from openvpn3_indicator.about import APPLICATION_NAME
from openvpn3_indicator.application import Application

###
#
# Main
#
###


def main():
    try:
        import setproctitle
        setproctitle.setproctitle(f'{APPLICATION_NAME}')
    except ImportError:
        logging.debug(traceback.format_exc())
        logging.error('Failed to import setproctitle module')
    application = Application()
    application.run(sys.argv)


if __name__ == '__main__':
    main()
