# -*- coding: utf-8 -*-
#
# Copyright (c) 2015 by Josh <josh@kaiju.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

#
# Log raw IRC messages to Mongo
#
# This script relies on the pymongo module installed in a virtualenv in
# ~/.weechat/python_env/. You can do this via:
#   $ virtualenv ~/.weechat/python_env/
#   $ ~/.weechat/python_env/bin/pip install pymongo
#
# After loading, configure your the Mongo hostname, port, database name
# and collection that you want to log to and then:
#   /set plugins.var.python.mongologger.enabled on
#

try:
    import weechat
except ImportError:
    raise RuntimeError("This script must be run via Weechat")

import sys, os, time, threading, re

SCRIPT_NAME = 'mongologger'
SCRIPT_AUTHOR = 'Josh <josh@kaiju.net>'
SCRIPT_VERSION = '0.2'
SCRIPT_LICENSE = 'GPL3'
SCRIPT_DESCRIPTION = 'Logs raw IRC traffic into a Mongo instance'
ENABLED = 'on'
DISABLED = 'off'
VENV_PATH = os.path.expanduser("~/.weechat/python_env/lib/python2.7/site-packages") 
HTTP_PATTERN = re.compile("(https?\:\/\/.*?)(?: |$)", re.IGNORECASE)

load_errors = []
config_defaults = {
    'enabled': DISABLED,
    'mongo_host': 'localhost',
    'mongo_port': '27017',
    'mongo_user': '',
    'mongo_password': '',
    'mongo_database': 'irclogs',
    'mongo_collection': 'messages'
}
logging_hooks = []
mongo_collection = None

# Bootstrap our local venv into sys.path
if os.path.exists(VENV_PATH):
    sys.path.append(VENV_PATH)
else:
    raise RuntimeError('Could not find a Python virtual environment in {}'.format(VENV_PATH))

import pymongo

def cleanup():
    """ Clean up after pymongo so we can safely unload """
    global mongo_collection

    if mongo_collection is not None:
        # Gracefully disconnect from MongoDB
        mongo_collection.database.client.close()

        # pymongo doesn't like to stop this thread on MongoClient.close() so we have to do it ourselves
        mongo_collection.database.client._kill_cursors_executor.close()

        mongo_collection = None

    # Wait for everything to die
    while threading.active_count() > 1:
        time.sleep(1)    

    return weechat.WEECHAT_RC_OK

def log_to_mongo(data, signal, raw_message):
    """ Parse a raw IRC message and insert it into a mongo collection """

    global mongo_collection

    parsed_message = weechat.info_get_hashtable('irc_message_parse', { 'message': raw_message })

    log_entry = {
        'server': signal.split(',')[0],
        'nick': parsed_message['nick'],
        'host': parsed_message['host'],
        'command': parsed_message['command'],
        'channel': parsed_message['channel'],
        'arguments': parsed_message['arguments']
    }

    if 'text' in parsed_message and len(parsed_message['text']) > 0:
        log_entry['text'] = parsed_message['text']
    elif log_entry['command'] == 'PRIVMSG':
        # fallback for pre-1.3 weechat
        log_entry['text'] = log_entry['arguments'].split(' :', 1)[-1]

    # denote any URLs
    if 'text' in log_entry and re.search(HTTP_PATTERN, log_entry['text']):
        log_entry['urls'] = re.findall(HTTP_PATTERN, log_entry['text'])

    mongo_collection.insert(log_entry)

    return weechat.WEECHAT_RC_OK

def enable_logging():
    """ Connect to MongoDB and add our IRC hooks """

    global mongo_collection, logging_hooks

    # Attempt to connect to our configured MongoDB instance
    # TODO -- assert that mongo connection worked
    mongo_host = weechat.config_get_plugin('mongo_host')
    mongo_port = weechat.config_get_plugin('mongo_port')
    mongo_database_name = weechat.config_get_plugin('mongo_database')
    mongo_collection_name = weechat.config_get_plugin('mongo_collection')
    mongo_user = weechat.config_get_plugin('mongo_user')
    mongo_password = weechat.config_get_plugin('mongo_password')

    mongoclient_arguments = {
        'connectTimeoutMS': 1
    }

    if len(mongo_host) > 0:
        mongoclient_arguments['host'] = mongo_host

    if len(mongo_port) > 0:
        mongoclient_arguments['port'] = int(mongo_port)

    mongo_client = pymongo.MongoClient(**mongoclient_arguments)
    mongo_database = mongo_client[mongo_database_name]
    mongo_collection = mongo_database[mongo_collection_name]

    # Authenticate if we have a configured user
    if len(mongo_user) > 0:
        try:
            mongo_database.authenticate(mongo_user, password=mongo_password)
        except pymongo.errors.OperationFailure as e:
            weechat.prnt('', 'Couldn\'t authenticate to MongoDB DB {}: {}'.format(mongo_database_name, e.details['errmsg']))
            weechat.config_set_plugin('enabled', DISABLED)
            return

    # Set up our logging hooks
    hooks = [
        'irc_raw_in2_privmsg',
        'irc_raw_in2_join',
        'irc_raw_in2_part',
        'irc_raw_in2_mode',
        'irc_raw_in2_quit',
        'irc_out1_privmsg',
        'irc_out1_join',
        'irc_out1_part',
        'irc_out1_mode',
        'irc_out1_quit'
    ]

    for hook in hooks:
        logging_hooks.append(weechat.hook_signal('*,{}'.format(hook), 'log_to_mongo', ''))

def disable_logging():
    """ Disable logging and clean up """

    global logging_hooks

    # Unset all our logging hooks
    for hook in logging_hooks:
        weechat.unhook(hook)

    logging_hooks = []

    cleanup()

def config_change_enabled(data, option, value):
    """ Turn on/off logging when we change the config value """

    if value == ENABLED:
        enable_logging()
    elif value == DISABLED:
        disable_logging()

    return weechat.WEECHAT_RC_OK

if __name__ == "__main__":

    weechat.register(SCRIPT_NAME,
                     SCRIPT_AUTHOR,
                     SCRIPT_VERSION,
                     SCRIPT_LICENSE,
                     SCRIPT_DESCRIPTION,
                     'cleanup',
                     '')

    # set any defaults we need to set
    for option, value in config_defaults.items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, value)

    # add a hook to enable/disable logging
    weechat.hook_config('plugins.var.python.{}.enabled'.format(SCRIPT_NAME), 'config_change_enabled', '')

    # enable logging if already configured
    if weechat.config_get_plugin('enabled') == ENABLED:
        enable_logging()

