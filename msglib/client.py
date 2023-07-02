from msglib.message import deserialize, serialize
from msglib.handlers import ChannelType, Command, QMsg


def publish_to_q(*, connection, q_id, payload):
    msg = QMsg(
            channel_type=ChannelType.QUEUE,
            q_id=q_id,
            command=Command.PUBLISH,
            payload=payload,
    )
    _publish(connection=connection, msg=msg)


def blocking_pull_subscribe_to_queue(*, connection, q_id):
    return _QSub(connection=connection, q_id=q_id)


class AckableQMsg:

    def __init__(self, payload):
        self.payload = payload

    def ack(self):
        pass


class _QSub:

    def __init__(self, *, connection, q_id):
        self._pull_msg = QMsg(
                channel_type=ChannelType.QUEUE,
                q_id=q_id,
                command=Command.PULL_MSG,
        )
        self._connection = connection

    def __next__(self):
        _publish(connection=self._connection, msg=self._pull_msg)
        msg_fields = deserialize(self._connection)
        return AckableQMsg(*msg_fields)


def _publish(*, connection, msg):
    connection.write(serialize(msg.to_bytes_tuple()))
