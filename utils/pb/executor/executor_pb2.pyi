from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ElectionRequest(_message.Message):
    __slots__ = ("sender_id",)
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    sender_id: int
    def __init__(self, sender_id: _Optional[int] = ...) -> None: ...

class ElectionResponse(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class CoordinatorRequest(_message.Message):
    __slots__ = ("leader_id", "become_leader")
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    BECOME_LEADER_FIELD_NUMBER: _ClassVar[int]
    leader_id: int
    become_leader: bool
    def __init__(self, leader_id: _Optional[int] = ..., become_leader: bool = ...) -> None: ...

class CoordinatorResponse(_message.Message):
    __slots__ = ("ok", "previous_leader")
    OK_FIELD_NUMBER: _ClassVar[int]
    PREVIOUS_LEADER_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    previous_leader: int
    def __init__(self, ok: bool = ..., previous_leader: _Optional[int] = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("leader_id",)
    LEADER_ID_FIELD_NUMBER: _ClassVar[int]
    leader_id: int
    def __init__(self, leader_id: _Optional[int] = ...) -> None: ...

class HeartbeatResponse(_message.Message):
    __slots__ = ("is_alive",)
    IS_ALIVE_FIELD_NUMBER: _ClassVar[int]
    is_alive: bool
    def __init__(self, is_alive: bool = ...) -> None: ...

class WriteRequest(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: int
    def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...

class WriteResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class ReadRequest(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: str
    def __init__(self, key: _Optional[str] = ...) -> None: ...

class ReadResponse(_message.Message):
    __slots__ = ("value",)
    VALUE_FIELD_NUMBER: _ClassVar[int]
    value: int
    def __init__(self, value: _Optional[int] = ...) -> None: ...

class StockRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StockResponse(_message.Message):
    __slots__ = ("all_items",)
    ALL_ITEMS_FIELD_NUMBER: _ClassVar[int]
    all_items: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, all_items: _Optional[_Iterable[str]] = ...) -> None: ...
