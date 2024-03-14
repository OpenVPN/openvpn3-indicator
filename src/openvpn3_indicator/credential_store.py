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
import secretstorage
import traceback

from openvpn3_indicator.about import APPLICATION_NAME, APPLICATION_TITLE

###
#
# CredentialStore
#
###


class CredentialStore:

    @property
    def application_name(self):
        return self._application_name

    @property
    def application_description(self):
        return self._application_description

    @property
    def secret_collection(self):
        if self._secret_collection is None:
            try:
                secret_connection = secretstorage.dbus_init()
                self._secret_collection = secretstorage.get_default_collection(secret_connection)
            except:  # TODO: Catch only expected exceptions
                logging.debug(traceback.format_exc())
                logging.error('Failed to connect with Secret Storage')
        return self._secret_collection

    @property
    def secret_collection_unlocked(self):
        collection = self.secret_collection
        if collection is not None:
            if collection.is_locked():
                try:
                    collection.unlock()
                    logging.info('Unlocked Secret Storage')
                except:  # TODO: Catch only expected exceptions
                    logging.debug(traceback.format_exc())
                    logging.error('Failed to unlock Secret Storage')
                    collection = None
        return collection

    def attrs(self):
        attrs = dict()
        attrs['application'] = self.application_name
        return attrs

    def __init__(self, application_name=APPLICATION_NAME, application_description=APPLICATION_TITLE):
        self._application_name = application_name
        self._application_description = application_description
        self._secret_collection = None

    def __getitem__(self, key):
        return self.Credentials(self, key)

    def keys(self):
        collection = self.secret_collection_unlocked
        result = set()
        if collection:
            try:
                for item in collection.search_items(self.attrs()):
                    config = item.get_attributes().get('config', None)
                    if config is not None:
                        result.add(config)
            except:  # TODO: Catch only expected exceptions
                logging.debug(traceback.format_exc())
                logging.error('Failed to list Secret Storage')
        return sorted(list(result))

    class Credentials:

        @property
        def parent(self):
            return self._parent

        @property
        def config_id(self):
            return self._config_id

        def __init__(self, parent, config_id):
            self._parent = parent
            self._config_id = str(config_id)

        def attrs(self, key=None):
            attrs = self.parent.attrs()
            attrs['config'] = self.config_id
            if key is not None:
                attrs['key'] = str(key)
            return attrs

        def label(self, key):
            key = str(key)
            return f'{self.parent.application_description} {self.config_id} {key}'

        def __setitem__(self, key, item):
            key = str(key)
            item = str(item)
            collection = self.parent.secret_collection_unlocked
            if collection:
                try:
                    label = self.label(key)
                    if item is not None:
                        collection.create_item(
                            label,
                            self.attrs(key),
                            bytes(str(item), 'utf-8'),
                            replace=True)
                        logging.info(f'Stored secret {label} in Secret Storage')
                    else:
                        for item in collection.search_items(self.attrs(key)):
                            item.delete()
                        logging.info(f'Removed secret {label} from Secret Storage')
                except:  # TODO: Catch only expected exceptions
                    logging.debug(traceback.format_exc())
                    logging.error('Failed to write to Secret Storage')

        def __getitem__(self, key):
            key = str(key)
            collection = self.parent.secret_collection_unlocked
            if collection:
                try:
                    items = list(collection.search_items(self.attrs(key)))
                    if len(items) > 1:
                        logging.warning(f'There are multiple entries for {self.label(key)} in Secret Storage')
                    if len(items) > 0:
                        return str(items[0].get_secret(), 'utf-8')
                    logging.info(f'Retrieved secret {self.label(key)} from Secret Storage')
                except:  # TODO: Catch only expected exceptions
                    logging.debug(traceback.format_exc())
                    logging.error('Failed to read from Secret Storage')

        def __delitem__(self, key):
            key = str(key)
            collection = self.parent.secret_collection_unlocked
            if collection:
                try:
                    for item in collection.search_items(self.attrs(key)):
                        item.delete()
                    logging.info(f'Removed secret {self.label(key)} from Secret Storage')
                except:  # TODO: Catch only expected exceptions
                    logging.debug(traceback.format_exc())
                    logging.error('Failed to delete from Secret Storage')

        def keys(self):
            collection = self.parent.secret_collection_unlocked
            result = set()
            if collection:
                try:
                    for item in collection.search_items(self.attrs()):
                        key = item.get_attributes().get('key', None)
                        if key is not None:
                            result.add(key)
                except:  # TODO: Catch only expected exceptions
                    logging.debug(traceback.format_exc())
                    logging.error('Failed to list Secret Storage')
            return sorted(list(result))
