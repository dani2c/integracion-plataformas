from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ProductoRequest(_message.Message):
    __slots__ = ("nombre", "descripcion", "precio", "stock_inicial", "foto")
    NOMBRE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPCION_FIELD_NUMBER: _ClassVar[int]
    PRECIO_FIELD_NUMBER: _ClassVar[int]
    STOCK_INICIAL_FIELD_NUMBER: _ClassVar[int]
    FOTO_FIELD_NUMBER: _ClassVar[int]
    nombre: str
    descripcion: str
    precio: float
    stock_inicial: int
    foto: bytes
    def __init__(self, nombre: _Optional[str] = ..., descripcion: _Optional[str] = ..., precio: _Optional[float] = ..., stock_inicial: _Optional[int] = ..., foto: _Optional[bytes] = ...) -> None: ...

class ProductoResponse(_message.Message):
    __slots__ = ("exito", "mensaje")
    EXITO_FIELD_NUMBER: _ClassVar[int]
    MENSAJE_FIELD_NUMBER: _ClassVar[int]
    exito: bool
    mensaje: str
    def __init__(self, exito: bool = ..., mensaje: _Optional[str] = ...) -> None: ...
