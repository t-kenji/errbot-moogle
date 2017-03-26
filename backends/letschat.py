# -*- coding: utf-8 -*-

import logging
import re

from errbot.backends.base import Message, ONLINE, Room, RoomOccupant, Person
from errbot.core import ErrBot


# Can't use __name__ because of Yapsy
log = logging.getLogger('errbot.backends.letschat')


try:
    from socketIO_client import SocketIO, BaseNamespace
    from socketIO_client.namespaces import find_callback
    from socketIO_client.parsers import format_socketIO_packet_data
except ImportError:
    log.exception("Could not start the lets-chat back-end")
    log.fatal(
            "You need to install the socketIO_client support in order to use the lets-chat."
            "You can do `pip install errbot socketIO_client` to install it."
    )
    sys.exit(1)


class LetschatClient():
    """
    """

    class LetschatNamespace(BaseNamespace):
        """
        """

        def __init__(self, io, path):
            """
            """

            super().__init__(io, path)
            self._user = None
            self._connected = False
            self._room = None

        def on_connect(self, *args):
            self._io.emit('account:whoami', self.on_account_whoami_response)

        def on_account_whoami_response(self, *args):
            self._user = dict(args[0])

            if not self._connected:
                log.info('Connected')
                self._connected = True

        def on_rooms_join_response(self, *args):
            log.info('Joined {}'.format(args[0].get('name')))
            self._room = dict(args[0])

        @property
        def user(self):
            return self._user

        @property
        def room(self):
            return self._room

        @property
        def connected(self):
            return self._connected

    def __init__(self, hostname, port, token):
        """
        """

        self._sio = SocketIO(hostname, port, LetschatClient.LetschatNamespace,
                             params={'token': token})
        self.on_users_join_handler = None
        self.on_messages_new_handler = None

    def wait(self, seconds=None):
        self._sio.wait(seconds)

    def emit_messages_create(self, message):
        self._sio.emit('messages:create', message)

    def emit_rooms_join(self, room):
        self._sio.emit('rooms:join', room, self._sio.get_namespace().on_rooms_join_response)

    @property
    def on_users_join_handler(self):
        return self._on_users_join_handler

    @on_users_join_handler.setter
    def on_users_join_handler(self, handler):
        self._on_users_join_handler = handler
        self._sio.on('users:join', self.on_users_join_handler)
        return True

    @property
    def on_messages_new_handler(self):
        return self._on_messages_new_handler

    @on_messages_new_handler.setter
    def on_messages_new_handler(self, handler):
        self._on_messages_new_handler = handler
        self._sio.on('messages:new', self._on_messages_new_handler)
        return True

    @property
    def username(self):
        return self._sio.get_namespace().user.get('username')

    @property
    def connected(self):
        return self._sio.get_namespace().connected

class LetschatPerson(Person):
    """
    """

    def __init__(self, client, username, roomid=None):
        """
        """
        self._client = client
        self._username = username
        self._roomid = roomid

    @property
    def username(self):
        return self._username

    @property
    def roomid(self):
        return self._roomid

    # Compatibility with the generic API.
    client = roomid
    nick = username

    # Override for ACLs

    @property
    def aclattr(self):
        return '@{}'.format(self.username)

    @property
    def fullname(self):
        """
        """
        log.info('LetschatPerson.fullname')
        return self._username

    def __unicode__(self):
        return '@{}'.format(self.username)

    def __str__(self):
        return self.__unicode__()

    def __eq__(self, other):
        if not isinstance(other, LetschatPerson):
            log.warn('tried to compare a LetschatPerson with a {}'.format(type(other)))
            return False
        return other.username == self.username

    @property
    def person(self):
        return '@{}'.format(self.username)

class LetschatRoomOccupant(RoomOccupant, LetschatPerson):
    """
    """

    def __init__(self, client, username, roomname, bot):
        """
        """

        super().__init__(client, username, roomname)
        log.info('LetschatRoomOccupant.__init__')
        self._room = LetschatRoom(roomname, bot=bot)

    @property
    def room(self):
        return self._room

class LetschatBackend(ErrBot):
    """
    """

    def __init__(self, config):
        """
        """

        super().__init__(config)
        log.info('LetschatBackend.__init__')
        identity = config.BOT_IDENTITY
        protocol = config.LCB_PROTOCOL
        hostname = config.LCB_HOSTNAME
        port = config.LCB_PORT
        self.token = identity.get('token', None)
        if not self.token:
            log.fatal(
                    'You need to set your token in the BOT_IDENTITY setting '
                    'in your config.py.'
            )
            sys.exit(1)

        self.client = LetschatClient(hostname, port, self.token)
        self.client.on_users_join_handler =  self._on_users_join_message
        self.client.on_messages_new_handler = self._on_messages_new_message

    def _on_users_join_message(self, *args):
        """
        """
        log.info('on users:join message: {}'.format(args))

    def _on_messages_new_message(self, *args):
        """
        """
        for message in args:
            log.info('message: {}'.format(message))
            self._message_handler(message)

    def _message_handler(self, message):
        """
        """
        room = message.get('room', {}).get('id')
        text = message.get('text', '')
        owner = message.get('owner', {}).get('username')

        text, mentioned = self._separate_text_and_mentioned(text)

        msg = Message(text)
        msg.frm = LetschatPerson(self.client, owner, room)
        if self.bot_identifier in mentioned:
            msg.to = self.bot_identifier
        else:
            log.debug('no mentiond to bot: {}'.format(text))
            msg.to = self.bot_identifier

        self.callback_message(msg)

        if mentioned:
            self.callback_mention(msg, mentioned)

    def _separate_text_and_mentioned(self, text):
        """
        """
        mentioned = []

        m = re.findall('@[0-9a-zA-Z]+', text)

        for user in m:
            try:
                identifier = self.build_identifier(user)
            except Exception as e:
                log.debug("Tried to build an identifier from '{}' but got exception: {}".format(user, e))
                continue

            # We only trac mentions of persons.
            if isinstance(identifier, LetschatPerson):
                log.debug('{} mentioned'.format(identifier))
                mentioned.append(identifier)
                text = text.replace(user, str(identifier))

        return text, mentioned

    def build_reply(self, mess, text=None, private=False):
        """
        """
        log.info('LetschatBackend.build_reply')

        response = self.build_message(text)
        response.frm = self.bot_identifier
        response.to = mess.frm

        return response

    def prefix_groupchat_reply(self, message, identifier):
        """
        """
        log.info('LetschatBackend.prefix_groupchat_reply')

        message.body = '@{} {}'.format(identifier.username, message.text)

    def build_message(self, text):
        """
        """

        message = super().build_message(text)
        log.info('LetschatBackend.build_message')

        return message

    def build_identifier(self, text_repf):
        """
        """
        log.info('LetschatBackend.build_identifier')

        text = text_repf.strip()

        if text.startswith('@') and '#' not in text:
            return LetschatPerson(self.client, text.split('@')[1])
        elif '#' in text:
            username, roomname = text.split('#')
            return LetschatRoomOccupant(username.split('@')[1], roomname, bot=self)

        raise RuntimeError('Unrecognized identifier: {}'.format(text))

    def serve_forever(self):
        """
        """
        log.info('LetschatBackend.serve_forever in')
        while not self.client.connected:
            self.client.wait(seconds=1)
        username = self.client.username

        self.bot_identifier = LetschatPerson(self.client, username)

        self.connect_callback()

        try:
            self.client.wait()
        except EOFError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            log.info('LetschatBackend.serve_forever out')
            self.disconnect_callback()
            self.shutdown()

    def send_message(self, mess):
        """
        """
        super().send_message(mess)
        try:
            if isinstance(mess.to, RoomOccupant):
                log.debug('This is a divert to private ...')
            to_room_id = mess.to.roomid

            message = {
                'room': to_room_id,
                'text': mess.body,
            }

            self.client.emit_messages_create(message)
        except Exception:
            log.exception(
                'An exception occurred while trying to send the following message '
                'to {}: {}'.format(mess.to, mess.body)
            )

    def connect(self):
        """
        """
        log.info('LetschatBackend.connect')
        return self.client

    def query_room(self, room):
        """
        """
        log.info('LetschatBackend.query_room: {}'.format(room))
        return LetschatRoom(room, bot=self)

    @property
    def mode(self):
        """
        """
        log.info('LetschatBackend.mode')
        return 'letschat'

    @property
    def rooms(self):
        """
        """
        log.info('LetschatBackend.rooms')
        return []

    def change_presence(self, status=ONLINE, message=''):
        """
        """
        super().change_presence(status=status, message=message)
        log.info('LetschatBackend.change_presence')

class LetschatRoom(Room):
    """
    """

    def __init__(self, name, bot):
        """
        """
        log.info('LetschatRoom.__init__: {}'.format(name))
        self._name = name
        self._bot = bot

    def join(self, username=None, password=None):
        """
        """
        log.info('LetschatRoom.join: {}, {}'.format(username, password))
        self._bot.client.emit_rooms_join(self._name)

    def leave(self, reason=None):
        """
        """
        log.info('LetschatRoom.leave')

    def create(self):
        """
        """
        log.info('LetschatRoom.create')

    def destroy(self):
        """
        """
        log.info('LetschatRoom.destroy')

    @property
    def exists(self):
        """
        """
        log.info('LetschatRoom.exists')
        return True

    @property
    def joined(self):
        """
        """
        log.info('LetschatRoom.joined')
        return True

    @property
    def topic(self):
        """
        """
        log.info('LetschatRoom.topic')
        return 'This is topic'

    @topic.setter
    def topic(self, topic):
        """
        """
        log.info('LetschatRoom.topic.setter')
        return True

    @property
    def occupants(self):
        """
        """
        log.info('LetschatRoom.occupants')
        return []

    def invite(self, *args):
        """
        """
        log.info('LetschatRoom.invite')
