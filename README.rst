======
msglib
======

Picking a message broker requires accepting various design choices
of its authors. You write client side code, server side code and the
broker makes things happen. This library is an experiment to see
if a different way is feasible - one where you have finer control
over what the broker does: you write client, server and broker code.


Usage example
=============

Let's look at 2 unit tests.

.. code-block:: python

    def test_publish_one_read_one_in_memory():

        # This is responsible for exchanging messages in memory
        memory_transport = msglib.ios.io_memory.Transport()

        # We need to identify the broker
        broker_endpoint = 'broker'

        # We also need to identify queues
        class QueueId(int, enum.Enum):
            GREETINGS = enum.auto()

        with (
            msglib.broker.Broker(
                # When a new client connects or writes
                # the broker needs to handle it.
                # This is where the broker's messaging logic lives.
                handler=msglib.handlers.ConnectionHandler(),

                # Object that provides means to talk to the world.
                connection_manager=msglib.ios.io_memory.InMemoryConnectionManager(
                    transport=memory_transport,
                    endpoint_id=broker_endpoint,
                ),
            ) as broker,
            memory_transport.connect(broker_endpoint) as sender_connection,
            memory_transport.connect(broker_endpoint) as receiver_connection,
        ):
            msglib.client.publish_to_q(
                connection=sender_connection,
                q_id=QueueId.GREETINGS,
                payload=b'Hello, world!',
            )
            sub = msglib.client.blocking_pull_subscribe_to_queue(
                connection=receiver_connection,
                q_id=QueueId.GREETINGS,
            )

            # We don't necessarily know how many low level messages
            # need to travel "on the wire" to send a message, subscribe,
            # receive the message. So we just keep processing
            # until the message is received. To avoid the test
            # getting stuck in the infinite loop, in case
            # of a bug or druing refactoring, there is an arbitrary
            # upper bound of the number of iterations.
            # Note that, because this in memory implementation is
            # intended to be used in a test environment, the blocking
            # methods do not in fact block, but instead raise
            # `BlockingIOError` in a blocking situation.
            for _ in range(10):
                broker.process_connections()
                try:
                    msg = next(sub)
                except BlockingIOError:
                    continue
                break
            else:
                raise AssertionError('Did not receive an expected message.')

            assert msg.payload == b'Hello, world!'
            msg.ack()


    def test_publish_one_read_one_sockets():

        broker_port = 12345
        broker_ip = msglib.ios.io_sockets.IPv6.from_string('::1')

        class QueueId(int, enum.Enum):
            GREETINGS = enum.auto()

        with (
                msglib.broker.Broker(
                    handler=msglib.handlers.ConnectionHandler(),
                    connection_manager=msglib.ios.io_sockets.EpollSocketManager(
                            port=broker_port,
                            ip=broker_ip,
                            epoll_timeout_seconds=0.001,
                    )
                ) as broker,
                msglib.ios.io_sockets.connect(
                    ip=broker_ip,
                    port=broker_port,
                    # Add timeout, so that we don't block forever 
                    # in case of a failing test.
                    timeout_seconds=10,
                ) as sender_connection,
                msglib.ios.io_sockets.connect(
                    ip=broker_ip,
                    port=broker_port,
                    timeout_seconds=10,
                ) as receiver_connection,
        ):
            msglib.client.publish_to_q(
                connection=sender_connection,
                q_id=QueueId.GREETINGS,
                payload=b'Hello, world!',
            )
            sub = msglib.client.blocking_pull_subscribe_to_queue(
                connection=receiver_connection,
                q_id=QueueId.GREETINGS,
            )

            # Attempting to read an unavailalbe message would
            # block the main thread, so we run it in its own thread.
            class Reader(threading.Thread):

                msg: msglib.client.AckableQMsg

                def run(self):
                    self.msg = next(sub)

            reader = Reader()
            reader.start()

            # Run broker until the reader thread quits.
            while reader.is_alive():
                broker.process_connections()

            assert reader.msg.payload == b'Hello, world!'
            reader.msg.ack()


Both test cases execute the same logical scenario. A message is published
to a queue by one party and consumed by a different one.
The key point here is that the broker is created and run as part of these
tests.
