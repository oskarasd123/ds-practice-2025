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

class OrderData(_message.Message):
    __slots__ = ("card_nr", "order_amount", "items", "user_name", "user_contact")
    CARD_NR_FIELD_NUMBER: _ClassVar[int]
    ORDER_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    USER_NAME_FIELD_NUMBER: _ClassVar[int]
    USER_CONTACT_FIELD_NUMBER: _ClassVar[int]
    card_nr: str
    order_amount: float
    items: _containers.RepeatedScalarFieldContainer[str]
    user_name: str
    user_contact: str
    def __init__(self, card_nr: _Optional[str] = ..., order_amount: _Optional[float] = ..., items: _Optional[_Iterable[str]] = ..., user_name: _Optional[str] = ..., user_contact: _Optional[str] = ...) -> None: ...

class InitRequest(_message.Message):
    __slots__ = ("order_id", "data")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    data: OrderData
    def __init__(self, order_id: _Optional[int] = ..., data: _Optional[_Union[OrderData, _Mapping]] = ...) -> None: ...

class EventRequest(_message.Message):
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
