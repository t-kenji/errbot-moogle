# -*- coding: utf-8 -*-

import logging
import os

ROOTDIR = os.environ.get('ERRBOT_ROOTDIR') or os.environ.get('PWD')
BACKEND = 'Letschat'

LCB_PROTOCOL = os.environ.get('ERRBOT_LCB_PROTOCOL', 'http')
LCB_HOSTNAME = os.environ.get('ERRBOT_LCB_HOSTNAME', 'localhost')
LCB_PORT = os.environ.get('ERRBOT_LCB_PORT', 5000)
LCB_TOKEN = os.environ.get('ERRBOT_LCB_TOKEN', '')
LCB_ROOMS = os.environ.get('ERRBOT_LCB_ROOMS','').split(',')
LCB_ADMINS = os.environ.get('ERRBOT_LCB_ADMINS', '').split(',')
LCB_NAME = os.environ.get('ERRBOT_LCB_NAME', '')

BOT_DATA_DIR = r'{}/data'.format(ROOTDIR)
BOT_EXTRA_PLUGIN_DIR = '{}/plugins'.format(ROOTDIR)
BOT_EXTRA_BACKEND_DIR = '{}/backends'.format(ROOTDIR)

BOT_LOG_FILE = r'{}/errbot.log'.format(ROOTDIR)
BOT_LOG_LEVEL = logging.DEBUG

BOT_ADMINS = tuple(LCB_ADMINS)
BOT_IDENTITY = {
    'token': LCB_TOKEN,
}

CHATROOM_PRESENCE = tuple(LCB_ROOMS)
CHATROOM_FN = LCB_NAME
