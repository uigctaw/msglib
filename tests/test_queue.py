import threading
import time

from msglib.ios import EpollSocketManager, IPv6, Connection
from msglib.broker import Broker
from msglib.client import publish_to_q, blocking_pull_subscribe_to_queue
from msglib.handlers import ConnectionHandler


def test_publish_one_read_one():

    queue_id = 0
    broker_port = 12345
    broker_ip = IPv6.from_string('::1')

    handler = ConnectionHandler()

    with (
            Broker(
                    handler=handler,
                    connection_manager=EpollSocketManager(
                            port=broker_port,
                            ip=broker_ip,
                    )
            ) as broker,
            Connection(
                    ip=broker_ip,
                    port=broker_port,
            ) as sender_connection,
            Connection(
                    ip=broker_ip,
                    port=broker_port,
            ) as receiver_connection,
    ):
        publish_to_q(
            connection=sender_connection,
            q_id=queue_id,
            payload=b'foo',
        )
        sub = blocking_pull_subscribe_to_queue(
            connection=receiver_connection,
            q_id=queue_id,
        )
        msg = None

        def _get_msg():
            nonlocal msg
            msg = next(sub)

        threading.Thread(target=_get_msg).start()
        while not msg:
            broker.process_connections()
            time.sleep(0.01)
        assert msg.payload == b'foo'
        msg.ack()
