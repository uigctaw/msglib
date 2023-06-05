def _read_field(byte_reader):
    first_byte_seq = byte_reader.read(1)
    first_byte, = first_byte_seq
    if first_byte < 0b1000_0000:
        return first_byte_seq

    length = 0b0011_1111 & first_byte
    bytes_ = byte_reader.read(length)

    if first_byte & 0b0100_0000:
        length = int_from_bytes(bytes_)
        return byte_reader.read(length)
    else:
        return bytes_


def int_from_bytes(bytes_):
    return int.from_bytes(bytes_, byteorder='big', signed=False)


def deserialize(byte_reader):
    num_of_fields = int_from_bytes(_read_field(byte_reader))
    return [bytes(_read_field(byte_reader)) for _ in range(num_of_fields)]


def serialize(msg):
    num_fields = len(msg)
    serialized = [_field_to_bytes(int_to_bytes(num_fields))]
    for field in msg:
        serialized.append(_field_to_bytes(field))
    return b''.join(serialized)


def _field_to_bytes(field):
    length = len(field)
    if length == 1 and field[0] < 0b1000_0000:
        return field
    if length < 0b01_00_0000:
        field_length = 0b10_00_0000 | length
        return bytes([field_length]) + field

    length_as_bytes = int_to_bytes(length)
    length_of_length = len(length_as_bytes)
    assert length_of_length < 0b01_00_0000

    return bytes([0b11_00_0000 | length_of_length]) + length_as_bytes + field


def int_to_bytes(int_):
    num_bytes = 0
    tmp_int = int_
    while tmp_int:
        tmp_int >>= 8
        num_bytes += 1
    return int_.to_bytes(length=num_bytes or 1, byteorder='big', signed=False)


def to_byte_fields(*, envelope, payload):
    return [int_to_bytes(field) for field in envelope] + [payload]
