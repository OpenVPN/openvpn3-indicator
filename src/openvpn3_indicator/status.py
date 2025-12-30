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

import collections

from openvpn3.constants import StatusMinor

from openvpn3_indicator.about import APPLICATION_NAME

DEFAULT_ICON = f'{APPLICATION_NAME}-idle'
DEFAULT_DESCRIPTION = 'Unknown'

StatusDescription = collections.namedtuple(
        'StatusDescription',
        ['minor', 'name', 'icon', 'description']
    )

status_descriptions = dict()

def register_status(name, icon, description):
    if hasattr(StatusMinor, name):
        minor = getattr(StatusMinor, name)
        desc = StatusDescription(minor=minor, name=name, icon=icon, description=description)
        status_descriptions[minor] = desc

register_status('UNSET',                  'idle',       'Unknown')
register_status('CFG_ERROR',              'idle-error', 'Configuration error')
register_status('CFG_OK',                 'loading',    'Connecting')
register_status('CFG_INLINE_MISSING',     'idle-error', 'Configuration error')
register_status('CFG_REQUIRE_USER',       'loading',    'Authentication required')
register_status('CONN_INIT',              'loading',    'Connecting')
register_status('CONN_CONNECTING',        'loading',    'Connecting')
register_status('CONN_CONNECTED',         'active',     'Connected')
register_status('CONN_DISCONNECTING',     'loading',    'Disconnecting')
register_status('CONN_DISCONNECTED',      'idle',       'Disconnected')
register_status('CONN_FAILED',            'idle-error', 'Connection failed')
register_status('CONN_AUTH_FAILED',       'idle-error', 'Authentication failed')
register_status('CONN_RECONNECTING',      'loading',    'Connecting')
register_status('CONN_PAUSING',           'loading',    'Pausing')
register_status('CONN_PAUSED',            'paused',     'Paused')
register_status('CONN_RESUMING',          'loading',    'Connecting')
register_status('CONN_DONE',              'idle',       'Disconnected')
register_status('SESS_NEW',               'loading',    'Connecting')
register_status('SESS_BACKEND_COMPLETED', 'loading',    'Connecting')
register_status('SESS_REMOVED',           'idle',       'Disconnected')
register_status('SESS_AUTH_USERPASS',     'loading',    'Authentication required')
register_status('SESS_AUTH_CHALLENGE',    'loading',    'Authentication required')
register_status('SESS_AUTH_URL',          'loading',    'Authentication required')
register_status('PKCS11_SIGN',            'loading',    'Authentication required')
register_status('PKCS11_ENCRYPT',         'loading',    'Authentication required')
register_status('PKCS11_DECRYPT',         'loading',    'Authentication required')
register_status('PKCS11_VERIFY',          'loading',    'Authentication required')
register_status('PROC_STARTED',           'loading',    'Process started')
register_status('PROC_STOPPED',           'idle-error', 'Process stopped')
register_status('PROC_KILLED',            'idle-error', 'Process killed')


def get_status_icon(major, minor):
    if minor in status_descriptions:
        icon = status_descriptions[minor].icon
        if icon:
            return f'{APPLICATION_NAME}-{icon}'
    return DEFAULT_ICON


def get_status_description(major, minor):
    if minor in status_descriptions:
        description = status_descriptions[minor].description
        if description:
            return description
    return DEFAULT_DESCRIPTION
