from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EnqueueRequest(_message.Message):
    __slots__ = ("order_id", "priority", "items")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    priority: int
    items: _containers.RepeatedCompositeFieldContainer[OrderItem]
    def __init__(self, order_id: _Optional[str] = ..., priority: _Optional[int] = ..., items: _Optional[_Iterable[_Union[OrderItem, _Mapping]]] = ...) -> None: ...

class OrderItem(_message.Message):
    __slots__ = ("title", "ammount")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AMMOUNT_FIELD_NUMBER: _ClassVar[int]
    title: str
    ammount: int
    def __init__(self, title: _Optional[str] = ..., ammount: _Optional[int] = ...) -> None: ...

class EnqueueResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class DequeueRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DequeueResponse(_message.Message):
    __slots__ = ("order_id", "has_order", "items")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    HAS_ORDER_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    has_order: bool
    items: _containers.RepeatedCompositeFieldContainer[OrderItem]
    def __init__(self, order_id: _Optional[str] = ..., has_order: bool = ..., items: _Optional[_Iterable[_Union[OrderItem, _Mapping]]] = ...) -> None: ...
