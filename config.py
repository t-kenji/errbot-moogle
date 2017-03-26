# -*- coding: utf-8 -*-

import logging
import os

ROOTDIR = os.environ.get('ERRBOT_ROOTDIR') or os.environ.get('PWD')
BACKEND = 'Letschat'

LCB_PROTOCOL = os.environ.get('ERRBOT_LCB_PROTOCOL', 'http')
LCB_HOSTNAME = os.environ.get('ERRBOT_LCB_HOSTNAME', 'localhost')
LCB_PORT = os.environ.get('ERRBOT_LCB_PORT', 5000)

BOT_DATA_DIR = r'{}/data'.format(ROOTDIR)
BOT_EXTRA_PLUGIN_DIR = '{}/plugins'.format(ROOTDIR)
BOT_EXTRA_BACKEND_DIR = '{}/backends'.format(ROOTDIR)

BOT_LOG_FILE = r'{}/errbot.log'.format(ROOTDIR)
BOT_LOG_LEVEL = logging.DEBUG

BOT_ADMINS = ('@admin', )
BOT_IDENTITY = {
    'token': 'YOUR_TOKEN',
}

CHATROOM_PRESENCE = ('BOT_IN_ROOM',)
CHATROOM_FN = 'BOT_NAME'
