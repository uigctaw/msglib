from collections import deque
from contextlib import contextmanager
from typing import Hashable, NewType
import uuid

from msglib.broker import ConnectionsActivity

ConnectionId = NewType('ConnectionId', uuid.UUID)


class Transport:

    def __init__(self):
        self._on_connection_request = {}

    @contextmanager
    def connect(self, endpoint_id: Hashable):
        conn = _Connection()
        self._on_connection_request[endpoint_id](conn.acceptor)
        yield conn.initiator

    def register_on_connection_request(
            self, *, endpoint_id: Hashable, callback):
        self._on_connection_request[endpoint_id] = callback


class InMemoryConnectionManager:

    def __init__(self, *, endpoint_id: Hashable, transport: Transport):
        self._with_data_ids: set[ConnectionId] = set()
        self._new_connections: list[_ConnectionParty] = []
        self._closed_connection_ids: list[ConnectionId] = []
        transport.register_on_connection_request(
                endpoint_id=endpoint_id,
                callback=self._on_connection_request,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def _on_read(self, *, connection_id, has_more_data):
        if not has_more_data:
            self._with_data_ids.remove(connection_id)

    def _on_write(self, *, connection_id, num_bytes_written):
        if num_bytes_written:
            self._with_data_ids.add(connection_id)

    def _on_connection_request(self, new_connection):
        self._new_connections.append(new_connection)
        new_connection.register_on_read(self._on_read)
        new_connection.register_on_write(self._on_write)

    def get_activity(self):
        new = self._new_connections[:]
        self._new_connections.clear()
        closed = self._closed_connection_ids[:]
        self._closed_connection_ids.clear()
        return ConnectionsActivity(
            new=new,
            readable_ids=list(self._with_data_ids),
            closed_ids=closed,
        )


class ConnectionBuffer:

    def __init__(self, connection_id):
        self._dq: deque[int] = deque()
        self._on_write = None
        self._on_read = None
        self.connection_id = connection_id

    def read(self, num):
        ret = [self._dq.popleft() for _ in range(num)]
        if on_read := self._on_read:
            on_read(
                connection_id=self.connection_id, has_more_data=bool(self._dq))
        return ret

    def write(self, bytes_: bytes):
        self._dq.extend(bytes_)
        if on_write := self._on_write:
            on_write(
                connection_id=self.connection_id,
                num_bytes_written=len(bytes_),
            )

    def __len__(self):
        return len(self._dq)

    def register_on_write(self, callback):
        self._on_write = callback

    def register_on_read(self, callback):
        self._on_read = callback


def _get_connection_id():
    return ConnectionId(uuid.uuid4())


class _Connection:

    def __init__(self):

        initiator_buffer = ConnectionBuffer(connection_id=_get_connection_id())
        acceptor_buffer = ConnectionBuffer(connection_id=_get_connection_id())
        self.initiator = _ConnectionParty(
                own_buffer=initiator_buffer,
                counterparty_buffer=acceptor_buffer,
                connection_id=initiator_buffer.connection_id,
        )
        self.acceptor = _ConnectionParty(
                own_buffer=acceptor_buffer,
                counterparty_buffer=initiator_buffer,
                connection_id=acceptor_buffer.connection_id,
        )


class _ConnectionParty:

    def __init__(self, own_buffer, counterparty_buffer, connection_id):
        self._own_buffer = own_buffer
        self._counterparty_buffer = counterparty_buffer
        self.id = connection_id
        self.register_on_read = own_buffer.register_on_read
        self.register_on_write = own_buffer.register_on_write

    def write(self, bytes_):
        self._counterparty_buffer.write(bytes_)

    def read(self, num_bytes):
        buff = self._own_buffer
        if len(buff) < num_bytes:
            raise BlockingIOError()
        return self._own_buffer.read(num_bytes)
