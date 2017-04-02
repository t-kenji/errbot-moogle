# -*- coding: utf-8 -*-

import logging
import re
import threading
import functools

from errbot.backends.base import (
        Message, Presence, ONLINE, AWAY, Room, RoomOccupant, Person, 
        RoomError, RoomDoesNotExistError, UserDoesNotExistError,
)
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
    The LetschatClient makes API Calls to the Lets-chat Web API via websocket

    It also manages some of the Client state for Rooms that the associated token (User or Bot)
    is associated with.

    Init:
        :Args:
            hostname (str): lets-chat host.
            port (int): lets-chat using port.
            token (str): Your lets-chat Authentication token.
    """

    class LetschatNamespace(BaseNamespace):
        """
        Define socket.io client behavier for lets-chat
        """

        def __init__(self, io, path):
            super().__init__(io, path)
            self._user = None
            self._connected = False
            self._rooms = []
            self._joined_rooms = []

        def on_connect(self, *args):
            self._io.on('rooms:new', self.on_rooms_new_message)
            self._io.on('rooms:archive', self.on_rooms_archive_message)
            self._io.emit('account:whoami', self.on_account_whoami_response)

        def on_account_whoami_response(self, *args):
            self._user = dict(args[0])
            self._io.emit('rooms:list', self.on_rooms_list_response)

        def on_rooms_list_response(self, *args):
            self._rooms.clear()

            for room in args[0]:
                self._rooms.append(dict(room))

            if not self._connected:
                log.info('Connected')
                self._connected = True

        def on_rooms_join_response(self, *args):
            room = args[0]
            if room.get('id') in [room_.get('id') for room_ in self._rooms]:
                log.info('Joined {}'.format(room.get('name')))
                self._joined_rooms.append(room.get('id'))

        def on_rooms_create_response(self, *args):
            room = dict(args[0])
            self._rooms.append(room)

        def on_rooms_new_message(self, *args):
            room = dict(args[0])
            if not room.get('id') in [room_.get('id') for room_ in self._rooms]:
                log.info('Created {}'.format(room.get('name')))
                self._rooms.append(room)

        def on_rooms_archive_message(self, *args):
            room = [room for room in self._rooms if room.get('id') == args[0].get('id')]
            if room is not None:
                room = room[0]
                log.info('Archived {}'.format(room.get('name')))
                self._rooms.remove(room)

        def on_rooms_update_message(self, *args):
            room = [room for room in self._rooms if room.get('id') == args[0].get('id')]
            if room is not None:
                room = room[0]
                log.info('Updated {}'.format(room.get('name')))
                room['name'] = args[0].get('name')
                room['description'] = args[0].get('description')

        @property
        def username(self):
            return self._user.get('username')

        @property
        def rooms(self):
            return self._rooms

        @property
        def joined_rooms(self):
            joined_ = [room for room in self._rooms if room.get('id') in self._joined_rooms]
            return joined_

        @property
        def connected(self):
            return self._connected

    def __init__(self, hostname, port, token, protocol='http', callbacks={}):
        self._sio = SocketIO('{}://{}'.format(protocol, hostname), port,
                             LetschatClient.LetschatNamespace,
                             params={'token': token})
        self.on_users_join_handler = callbacks.get('on_users_join', None)
        self.on_users_leave_handler = callbacks.get('on_users_leave', None)
        self.on_messages_new_handler = callbacks.get('on_messages_new', None)

        # wait for connection sequence.
        while not self._sio.get_namespace().connected:
            self._sio.wait(seconds=1)

    def emit(self, event, *args, **kw):
        self._sio.emit(event, *args, **kw)

    def wait(self, seconds=None):
        self._sio.wait(seconds)

    def emit_messages_create(self, message):
        self.emit('messages:create', message)

    def emit_rooms_join(self, roomid):
        self.emit('rooms:join', roomid, self.server.on_rooms_join_response)

    def emit_rooms_leave(self, roomid):
        self.emit('rooms:leave', roomid)
        self.server._joined_rooms.remove(roomid)

    def emit_rooms_create(self, name):
        options = {
            'name': name,
            'slug': name,
        }
        self.emit('rooms:create', options, self.server.on_rooms_create_response)

    def emit_rooms_archive(self, roomid):
        room = [room for room in self.server._rooms if room.get('id') == roomid]
        if room is not None:
            options = {
                'id': roomid,
            }
            self.emit('rooms:archive', options)

    def emit_rooms_update(self, roomid, name=None, desc=None):
        room = [room for room in self.server._rooms if room.get('id') == roomid]
        if room is not None:
            options = dict(room[0])
            if name is not None:
                options['name'] = name
            if description is not None:
                options['description'] = desc
            self.emit('rooms:update', options)

    def emit_rooms_users(self, roomid):
        users = []
        def on_rooms_users_response(event, *args):
            for user in args[0]:
                users.append(dict(user))
            event.set()

        event_ = threading.Event()
        callback = functools.partial(on_rooms_users_response, event_)
        options = {
            'room': roomid,
        }
        self.emit('rooms:users', options, callback)
        event_.wait()

        return users

    def emit_users_list(self):
        users = []
        def on_users_list_response(event, *args):
            for user in args[0]:
                users.append(dict(user))
            event.set()

        event_ = threading.Event()
        callback = functools.partial(on_users_list_response, event_)
        self.emit('users:list', callback)
        event_.wait()

        return users

    @property
    def on_users_join_handler(self):
        return self._on_users_join_handler

    @on_users_join_handler.setter
    def on_users_join_handler(self, handler):
        self._on_users_join_handler = handler
        self._sio.on('users:join', self.on_users_join_handler)
        return True

    @property
    def on_users_leave_handler(self):
        return self._on_users_leave_handler

    @on_users_leave_handler.setter
    def on_users_leave_handler(self, handler):
        self._on_users_leave_handler = handler
        self._sio.on('users:leave', self.on_users_leave_handler)
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
    def server(self):
        return self._sio.get_namespace()

class LetschatPerson(Person):
    """
    This class describes a person on lets-chat's network.
    """

    def __init__(self, client, username, roomid=None):
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
    This class represents a person inside a room.
    """

    def __init__(self, client, username, roomid, bot):
        """
        This class represents a person inside a room.
        """

        super().__init__(client, username, roomid)
        self._room = LetschatRoom(roomid=roomid, bot=bot)

    @property
    def room(self):
        return self._room

    def __unicode__(self):
        return '#{}/{}'.format(self._room.slug, self.username)

    def __str__(self):
        return self.__unicode__()

    def __eq__(self, other):
        if not instance(other, RoomOccupant):
            log.warn('tried to compare a LetschatRoomOccupant with a LetschatParent {} vs {}'.format(self, other))
            return False
        return other.room.id == self.room.id and other.username == self.username

class LetschatBackend(ErrBot):
    """
    lets-chat bot core
    """

    def __init__(self, config):
        super().__init__(config)
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

        callbacks = {
            'on_users_join': self._on_users_join_message,
            'on_users_leave': self._on_users_leave_message,
            'on_messages_new': self._on_messages_new_message,
        }
        self.client = LetschatClient(hostname, port, self.token, protocol, callbacks=callbacks)

    def _on_users_join_message(self, *args):
        for event in args:
            event['status'] = ONLINE
            self._presence_change_event_handler(event)

    def _on_users_leave_message(self, *args):
        for event in args:
            event['status'] = AWAY
            self._presence_change_event_handler(event)

    def _on_messages_new_message(self, *args):
        for message in args:
            self._message_event_handler(message)

    def _presence_change_event_handler(self, event):
        """
        Event handler for the 'presence_change' event
        """
        user = LetschatPerson(self.client, event.get('username'))
        status = event.get('status')
        self.callback_presence(Presence(identifier=user, status=status))

    def _message_event_handler(self, message):
        """
        Event handler for the 'message' event
        """
        roomid = message.get('room', {}).get('id')
        text = message.get('text', '')
        owner = message.get('owner', {}).get('username')

        text, mentioned = self._extract_mentions_from(text)

        msg = Message(text)
        msg.frm = LetschatRoomOccupant(self.client, owner, roomid, self)
        if self.bot_identifier in mentioned:
            msg.to = self.bot_identifier
        else:
            msg.to = LetschatRoom(roomid=roomid, bot=self)

        self.callback_message(msg)

        if mentioned:
            self.callback_mention(msg, mentioned)

    def _extract_mentions_from(self, text):
        """
        Extract the mentions from the text
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
        Build a reply message object
        """
        response = self.build_message(text)
        response.frm = self.bot_identifier
        response.to = mess.frm

        return response

    def prefix_groupchat_reply(self, message, identifier):
        """
        Create a reply prefix for group chat
        """
        super().prefix_groupchat_reply(message, identifier)

        message.body = '@{} {}'.format(identifier.username, message.text)

    def build_message(self, text):
        """
        Build a message object
        """
        return super().build_message(text)

    def build_identifier(self, text_representation):
        """
        Build a :class:`LetschatIdentifier` from the given string text_representation.

        Supports strings with the formats accepted by
        :func:`~extract_identifiers_from_string`.
        """
        log.info('building an identifer from {}'.format(text_representation))

        text = text_representation.strip()

        if text.startswith('@') and '#' not in text:
            return LetschatPerson(self.client, text.split('@')[1])
        elif '#' in text:
            username, roomslug = text.split('#')
            roomid = self.roomslug_to_roomid(roomslug)
            return LetschatRoomOccupant(self.client, username.split('@')[1], roomid, bot=self)

        raise RuntimeError('Unrecognized identifier: {}'.format(text))

    def serve_forever(self):
        while not self.client.server.connected:
            try:
                self.client.wait(seconds=1)
            except:
                self.disconnect_callback()
                self.shutdown()
                raise Exception('Connection failed, invalid token?')

        username = self.client.server.username
        self.bot_identifier = LetschatPerson(self.client, username)
        self.connect_callback()

        try:
            self.client.wait()
        except EOFError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            self.disconnect_callback()
            self.shutdown()

    def roomid_to_roomslug(self, id_):
        """
        Convert a lets-chat room ID to its room slug
        """
        room = [room for room in self.client.server.rooms if room.get('id') == id_]
        if not room:
            raise RoomDoesNotExistError('No room with ID {} exists'.format(id_))
        return room[0].get('slug')

    def roomslug_to_roomid(self, slug):
        """
        Convert a lets-chat room slug to its room ID
        """
        slug = slug.lstrip('#')
        room = [room for room in self.client.server.rooms if room.get('slug') == slug]
        if not room:
            raise RoomDoesNotExistError('No room named {} exists'.format(slug))
        return room[0].get('id')

    def rooms_info(self, joined_only=False):
        """
        Get all rooms and return infomation about them.

        :param joined_only:
            Filter out rooms the bot hasn't joined
        :returns:
            A list of channel types.
        """
        rooms_ = []
        def on_rooms_list_response(event, *args):
            for room in args[0]:
                rooms_.append(room)
            event.set()

        event_ = threading.Event()
        callback = functools.partial(on_rooms_list_response, event_)

        self.client.emit('rooms:list', callback)
        event_.wait()

        return rooms_

    def send_message(self, mess):
        super().send_message(mess)
        try:
            if isinstance(mess.to, RoomOccupant):
                log.debug('This is a divert to private ...')
            to_roomid = mess.to.roomid

            message = {
                'room': to_roomid,
                'text': mess.body,
            }

            self.client.emit_messages_create(message)
        except Exception:
            log.exception(
                    'An exception occurred while trying to send the following message '
                    'to {}: {}'.format(mess.to, mess.body)
            )

    def shutdown(self):
        super().shutdown()

    def connect(self):
        return self.client

    def query_room(self, room):
        """
        Room can either be a slug or a roomid
        """
        m = re.match(r'^#(?P<slug>\w+)$', room)
        if m is not None:
            return LetschatRoom(slug=m.groupdict()['slug'], bot=self)

        return LetschatRoom(roomid=room, bot=self)

    @property
    def mode(self):
        return 'letschat'

    def rooms(self):
        """
        Return a list of rooms the bot is currently in.

        :returns:
            A list of :class:`~LetschatRoom` instances.
        """
        return [LetschatRoom(roomid=room.get('id'), bot=self) for room in self.client.server.joined_rooms]

    def change_presence(self, status=ONLINE, message=''):
        super().change_presence(status=status, message=message)

class LetschatRoom(Room):

    def __init__(self, slug=None, roomid=None, bot=None):
        if roomid is not None and slug is not None:
            raise ValueError('roomid and slug are mutually exclusive')

        if slug is not None:
            if slug.startswith('#'):
                self._slug = slug[1:]
            else:
                self._slug = slug
        else:
            self._slug = bot.roomid_to_roomslug(roomid)

        self._id = None
        self._bot = bot

    def __str__(self):
        return '#{}'.format(self.slug)

    @property
    def _room(self):
        """
        The room object exposed by LetschatClient
        """
        room = [room_ for room_ in self._bot.client.server.rooms if room_.get('slug') == self.slug]
        if not room:
            raise RoomDoesNotExistError(
                    "{} does not exist (or is a private room you don't have access to)".format(str(self))
            )
        return room[0]

    def join(self, username=None, password=None):
        try:
            log.info('Joining room {}'.format(str(self)))
            self._bot.client.emit_rooms_join(self.id)
        except Exception as e:
            raise RoomError(e)

    def leave(self, reason=None):
        try:
            log.info('Leaving room {} ({})'.format(str(self), self.id))
            self._bot.client.emit_rooms_leave(self.id)
        except Exception as e:
            raise RoomError(e)
        self._id = None

    def create(self, private=False):
        try:
            log.info('Creating room {}'.format(str(self)))
            self._bot.client.emit_rooms_create(self.slug)
        except Exception as e:
            raise RoomError(e)

    def destroy(self):
        try:
            log.info('Archiving room {}'.format(str(self)))
            self._bot.client.emit_rooms_archive(self.id)
        except Exception as e:
            raise RoomError(e)
        self._id = None

    @property
    def id(self):
        """
        Return the ID of this room
        """
        if self._id is None:
            self._id = self._room.get('id')
        return self._id

    @property
    def slug(self):
        """
        Return the slug of this room
        """
        return self._slug

    @property
    def exists(self):
        return len([room for room in self._bot.client.server.rooms if room_.get('slug') == self.slug]) > 0

    @property
    def joined(self):
        if self._id is None:
            return self._id in [room.get('id') for room in self._bot.client.server.joined_rooms]
        return False

    @property
    def topic(self):
        name = self._room.get('name', '')
        if name == '':
            return None
        else:
            return name

    @topic.setter
    def topic(self, topic):
        log.info("Setting topic of {} ({}) to '{}'".format(str(self), self.id, topic))
        self._bot.client.emit_rooms_update(self.id, name=topic)

    @property
    def occupants(self):
        users = self._bot.client.emit_rooms_users(self.id)
        return [LetschatRoomOccupant(self._bot.client, user, self.id, self._bot) for user in users]

    def invite(self, *args):
        users = {user.get('username'): user.get('id') for user in self._bot.client.emit_users_list()}
        for user in args:
            if user not in users:
                raise UserDoesNotExistError("User '{}' not found".format(user))
            log.info('Inviting {} into {} ({})'.format(user, str(self), self.id))
        raise RuntimeError('Invite not support')

    def __eq__(self, other):
        if not instance(other, LetschatRoom):
            return False
        return self.id == other.id
