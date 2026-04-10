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

class EventDoneRequest(_message.Message):
    __slots__ = ("order_id", "event_name", "clock", "failed", "error_msg", "is_fraud")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_NAME_FIELD_NUMBER: _ClassVar[int]
    CLOCK_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    ERROR_MSG_FIELD_NUMBER: _ClassVar[int]
    IS_FRAUD_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    event_name: str
    clock: VectorClock
    failed: bool
    error_msg: str
    is_fraud: bool
    def __init__(self, order_id: _Optional[int] = ..., event_name: _Optional[str] = ..., clock: _Optional[_Union[VectorClock, _Mapping]] = ..., failed: bool = ..., error_msg: _Optional[str] = ..., is_fraud: bool = ...) -> None: ...

class suggestionsDoneRequest(_message.Message):
    __slots__ = ("order_id", "suggestions", "clock")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SUGGESTIONS_FIELD_NUMBER: _ClassVar[int]
    CLOCK_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    suggestions: _containers.RepeatedScalarFieldContainer[str]
    clock: VectorClock
    def __init__(self, order_id: _Optional[int] = ..., suggestions: _Optional[_Iterable[str]] = ..., clock: _Optional[_Union[VectorClock, _Mapping]] = ...) -> None: ...
