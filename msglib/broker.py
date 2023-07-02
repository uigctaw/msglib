from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Hashable, Protocol, TypeAlias

from msglib.message import deserialize, serialize


ConnectionId: TypeAlias = Hashable
Message: TypeAlias = Sequence[bytes]


class Connection(Protocol):

    def read(self, num_bytes) -> bytes:
        pass

    def write(self, bytes_):
        pass


@dataclass(kw_only=True, frozen=True, slots=True)
class ConnectionsActivity:
    new: Iterable[Connection]
    readable_ids: Iterable[ConnectionId]
    closed_ids: Iterable[ConnectionId]


class ConnectionHandler(Protocol):

    def on_new_connection(self, connection: ConnectionId):
        pass

    def on_connection_closed(self, connection: ConnectionId):
        pass

    def on_message(self, msg: Message) -> Message | None:
        pass


class ConnectionManager(Protocol):

    def __enter__(self) -> ConnectionManager:
        pass

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None:
        pass

    def get_activity(self) -> ConnectionsActivity:
        pass


class Broker:

    def __init__(self, *, handler, connection_manager):
        self._connection_manager = connection_manager
        self._connections = {}
        self._handler = handler

    def __enter__(self):
        self._connection_manager.__enter__()
        return self

    def __exit__(self, *args):
        return self._connection_manager.__exit__(*args)

    def process_connections(self):
        connections = self._connection_manager.get_activity()
        for new in connections.new:
            self._connections[new.id] = new
            self._handler.on_new_connection(new.id)
        for readable_id in connections.readable_ids:
            self._process_message(self._connections[readable_id])
        for closed_id in connections.closed_ids:
            del self._connections[closed_id]
            self._handler.on_connection_closed(closed_id)

    def _process_message(self, connection):
        msg_fields = deserialize(connection)
        if (to_reply := self._handler.on_message(msg_fields=msg_fields)):
            connection.write(serialize(to_reply))
