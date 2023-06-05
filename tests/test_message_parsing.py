from msglib.message import deserialize, serialize


class ByteReader:

    def __init__(self, bytes_):
        self._bytes = iter(bytes_)

    def read(self, num_bytes):
        read = []
        for _ in range(num_bytes):
            read.append(next(self._bytes))
        return read


def test_zero_fields_msg():
    msg = [0]
    deserialized = deserialize(ByteReader(msg))
    assert deserialized == []
    assert serialize(deserialized) == bytes(msg)


def test_one_field_msg_with_low_field_value():
    for field in [
            0,
            0b0111_1111,  # max value for one byte field
    ]:
        msg = [
                1,  # 1 field
                field,
        ]
        deserialized = deserialize(ByteReader(msg))
        assert deserialized == [bytes([field])]
        assert serialize(deserialized) == bytes(msg)


def test_one_field_msg_with_mid_field_value():
    for length, field in [

            # max value for one byte field + 1
            (0b1000_0001, bytes([0b1000_0000])),

            # max value for field with length
            # described with one byte
            (0b1011_1111, bytes([255] * 63)),

    ]:
        msg = [
                1,  # 1 field
                length,
                *field,
        ]
        deserialized = deserialize(ByteReader(msg))
        assert deserialized == [field]
        assert serialize(deserialized) == bytes(msg)


def test_one_field_msg_with_high_field_value():
    field = bytes([255] * 63) + bytes([0])
    msg = [
            1,  # 1 field
            0b11_00_0001,  # length of length field is 1
            0b0100_0000,  # length of payload is 64
            *field,
    ]
    deserialized = deserialize(ByteReader(msg))
    assert deserialized == [field]
    assert serialize(deserialized) == bytes(msg)


def test_300_field_msg():
    msg = [
            0b10_00_0010,  # length of value is 2
            0b00_00_0001,  # 2 ** 8 +
            0b00_10_1100,  # + 44 = 300
    ] + [3] * 300
    deserialized = deserialize(ByteReader(msg))
    assert deserialized == [bytes([3])] * 300
    assert serialize(deserialized) == bytes(msg)
