from collections.abc import Iterable
from dataclasses import dataclass
from typing import NewType
import select
import socket


ConnectionId = NewType('ConnectionId', int)


class InvalidIPv6(Exception):
    pass


class IPv6(tuple):

    def __new__(cls, *eight_quartets: int):
        if len(eight_quartets) != 8:
            raise InvalidIPv6(
                    f'{eight_quartets}: IPv6 address has 8 quartets.')
        max_quartet = 2 ** 16 - 1
        for quartet in eight_quartets:
            if not 0 <= quartet <= max_quartet:
                raise InvalidIPv6(
                        f'{quartet}: quartet should be between'
                        + f' 0 and {max_quartet} (inclusive).'
                )

        # mypy bug
        return super().__new__(cls, eight_quartets)  # type: ignore

    @classmethod
    def from_string(cls, string):
        assert string == '::1'
        return cls(0, 0, 0, 0, 0, 0, 0, 1)

    def __str__(self):
        return ':'.join(f'{quartet:04X}' for quartet in self)


@dataclass(frozen=True, kw_only=True, slots=True)
class IPv6ConnectArgs:
    host: IPv6
    port: int

    def __iter__(self):
        return iter((
            str(self.host),
            self.port,
            0,  # sin6_flowinfo
            0,  # sin6_scope_id
        ))


class Connection:

    def __init__(self, *, ip: IPv6, port: int):
        self._socket: socket.socket
        self._ip = ip
        self._port = port

    def __enter__(self):
        self._socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        self._socket.__enter__()
        self._socket.connect(
                tuple(IPv6ConnectArgs(host=self._ip, port=self._port)))
        return self

    def __exit__(self, *args):
        self._socket.__exit__(*args)

    def read(self, num_bytes):
        return self._socket.recv(num_bytes)

    def write(self, bytes_):
        return self._socket.sendall(bytes_)


class InitializedConnection:

    def __init__(self, socket_):
        self._socket = socket_
        self.id = socket_.fileno()

    def read(self, num_bytes):
        return self._socket.recv(num_bytes)

    def write(self, bytes_):
        return self._socket.sendall(bytes_)


class EpollSocketManager:

    def __init__(self, ip: IPv6, port: int):
        self._ip = ip
        self._port = port
        self._listen_socket: socket.socket
        self._epoll: select.epoll

    def __enter__(self):
        self._listen_socket = socket.socket(
                socket.AF_INET6, socket.SOCK_STREAM)
        self._listen_socket.setsockopt(
                socket.SOL_SOCKET,  # level
                socket.SO_REUSEADDR,  # optname
                1,  # value
        )
        self._listen_socket.bind(
                tuple(IPv6ConnectArgs(host=self._ip, port=self._port)))
        self._listen_socket.listen(10)
        self._listen_socket.setblocking(False)

        self._epoll = select.epoll()
        self._epoll.register(self._listen_socket.fileno(), select.EPOLLIN)

        return self

    def __exit__(self, *args):
        self._epoll.unregister(self._listen_socket.fileno())
        self._epoll.close()
        self._listen_socket.close()

    def get_activity(self):
        epoll_ = self._epoll
        listen_socket = self._listen_socket

        new_connections = []
        readable = []
        closed = []
        events = epoll_.poll(0)
        for fileno, event in events:
            fileno = ConnectionId(fileno)
            if fileno == listen_socket.fileno():
                connection, _ = listen_socket.accept()
                connection.setblocking(False)
                epoll_.register(connection.fileno(), select.EPOLLIN)
                new_connections.append(InitializedConnection(connection))
            else:
                processed = False
                if event & select.EPOLLIN:
                    readable.append(fileno)
                    processed = True
                if event & select.EPOLLHUP:
                    epoll_.unregister(fileno)
                    closed.append(fileno)
                    processed = True
                if not processed:
                    raise ValueError(f'Unexpected event {event}')
        return Connections(
                new=new_connections,
                readable_ids=readable,
                closed_ids=closed,
        )


@dataclass(kw_only=True, frozen=True, slots=True)
class Connections:
    new: Iterable[InitializedConnection | Connection]
    readable_ids: Iterable[ConnectionId]
    closed_ids: Iterable[ConnectionId]
