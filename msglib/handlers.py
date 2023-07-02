from collections import defaultdict
from enum import Enum, auto
from queue import Queue
from typing import NamedTuple

from msglib.message import int_from_bytes, int_to_bytes


class _Queue:

    def __init__(self):
        self._q: Queue[bytes] = Queue()

    def put(self, payload):
        self._q.put(payload)

    def get(self):
        return self._q.get()


class QueueHandler:

    def __init__(self):
        self._qs = defaultdict(_Queue)

    def __call__(self, msg_tail):
        command, q_id, *tail = msg_tail
        q_id = int_from_bytes(q_id)
        match int_from_bytes(command):
            case Command.PUBLISH:
                payload, = tail
                return self._handle_publish(q_id, payload=payload)
            case Command.PULL_MSG:
                return self._handle_pull_msg(q_id)

    def _handle_publish(self, q_id, *, payload):
        self._qs[q_id].put(payload)

    def _handle_pull_msg(self, q_id):
        return (self._qs[q_id].get(),)


class ConnectionHandler:

    def __init__(self):
        self._handlers = {
            ChannelType.QUEUE: QueueHandler(),
        }

    def on_new_connection(self, connection_id):
        print(connection_id)

    def on_message(self, *, msg_fields):
        channel_type, *tail = msg_fields
        return self._handlers[int_from_bytes(channel_type)](
                tail,
        )


class ChannelType(int, Enum):
    QUEUE = auto()


class Command(int, Enum):
    PUBLISH = auto()
    PULL_MSG = auto()


class QMsg(NamedTuple):

    channel_type: ChannelType
    command: Command
    q_id: int
    payload: bytes | None = None

    def to_bytes_tuple(self):
        return (
            int_to_bytes(self.channel_type),
            int_to_bytes(self.command),
            int_to_bytes(self.q_id),
        ) + ((self.payload,) if self.payload else ())
