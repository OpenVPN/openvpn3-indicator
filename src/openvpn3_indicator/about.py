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


APPLICATION_NAME = 'openvpn3-indicator'
APPLICATION_TITLE = 'OpenVPN3 Indicator'
APPLICATION_ID = 'net.openvpn.openvpn3_indicator'
APPLICATION_SYSTEM_TAG = 'openvpn3-indicator'
APPLICATION_AUTHORS = [
        'Grzegorz Gutowski <grzegorz.gutowski@uj.edu.pl>',
    ]
APPLICATION_URL = 'https://github.com/OpenVPN/openvpn3-indicator'
APPLICATION_VERSION = '0.1'
BACKEND_VERSION_MINIMUM = 20
BACKEND_VERSION_RECOMMENDED = 21
APPLICATION_DESCRIPTION_SHORT = 'Simple indicator application for OpenVPN3'
APPLICATION_DESCRIPTION_LONG = '''
This is a simple indicator application that controls OpenVPN3 tunnels.
It is based on D-Bus interface provided by OpenVPN3 Linux client.
It is a temporary solution until Network Manager supports OpenVPN3.
'''.strip()
CONFIGURATION_MIME_TYPE = 'application/x-openvpn-profile'
