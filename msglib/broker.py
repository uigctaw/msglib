from msglib.message import deserialize, serialize


class Broker:

    def __init__(self, *, handler, connection_manager):
        """
        Params
        ------
        handlers:
            Maps message types to handlers for these types.
        connections:
            Container giving access to connections with
            various types of activity on them.
        """
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
            self._handler.new_connection(new.id)
        for readable_id in connections.readable_ids:
            self._process_message(self._connections[readable_id])
        for closed_id in connections.closed_ids:
            del self._connections[closed_id]
            self._handler.closed(closed_id)

    def _process_message(self, connection):
        msg_fields = deserialize(connection)
        if (to_reply := self._handler.handle_message(msg_fields=msg_fields)):
            connection.write(serialize(to_reply))
