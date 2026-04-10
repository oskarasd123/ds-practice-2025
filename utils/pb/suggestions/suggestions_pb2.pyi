from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class VectorClock(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, values: _Optional[_Iterable[int]] = ...) -> None: ...

class InitRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    def __init__(self, order_id: _Optional[int] = ...) -> None: ...

class getSuggestionsRequest(_message.Message):
    __slots__ = ("order_id", "clock")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLOCK_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    clock: VectorClock
    def __init__(self, order_id: _Optional[int] = ..., clock: _Optional[_Union[VectorClock, _Mapping]] = ...) -> None: ...

class ClearRequest(_message.Message):
    __slots__ = ("order_id", "final_clock")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FINAL_CLOCK_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    final_clock: VectorClock
    def __init__(self, order_id: _Optional[int] = ..., final_clock: _Optional[_Union[VectorClock, _Mapping]] = ...) -> None: ...
