from __future__ import annotations

import sys
from decimal import Decimal
from math import copysign, inf, nextafter
from typing import TYPE_CHECKING, TypeVar, get_args

from annotated_types import Ge, Gt, Le, Lt
from bec_lib.logger import bec_logger
from pydantic_core import PydanticUndefined

if TYPE_CHECKING:  # pragma: no cover
    from pydantic.fields import FieldInfo

logger = bec_logger.logger


_MININT = -2147483648
_MAXINT = 2147483647
_MINFLOAT = -sys.float_info.max
_MAXFLOAT = sys.float_info.max

T = TypeVar("T", int, float, Decimal)


def field_limits(info: FieldInfo, type_: type[T], prec: int | None = None) -> tuple[T, T]:
    def _nextafter(x, y):
        return nextafter(x, y) if prec is None else x + (10 ** (-prec)) * (copysign(1, y))

    _min = _MININT if type_ is int else _MINFLOAT
    _max = _MAXINT if type_ is int else _MAXFLOAT
    for md in info.metadata:
        if isinstance(md, Ge):
            _min = type_(md.ge)  # type: ignore
        if isinstance(md, Gt):
            _min = type_(md.gt) + 1 if type_ is int else _nextafter(type_(md.gt), inf)  # type: ignore
        if isinstance(md, Lt):
            _max = type_(md.lt) - 1 if type_ is int else _nextafter(type_(md.lt), -inf)  # type: ignore
        if isinstance(md, Le):
            _max = type_(md.le)  # type: ignore
    return _min, _max  # type: ignore


def _get_anno(info: FieldInfo, annotation: str, default):
    for md in info.metadata:
        if hasattr(md, annotation):
            return getattr(md, annotation)
    return default


def field_precision(info: FieldInfo):
    return _get_anno(info, "decimal_places", 307)


def field_maxlen(info: FieldInfo):
    return _get_anno(info, "max_length", None)


def field_minlen(info: FieldInfo):
    return _get_anno(info, "min_length", None)


def field_default(info: FieldInfo):
    if info.default is PydanticUndefined:
        return
    return info.default


def clearable_required(info: FieldInfo):
    return type(None) in get_args(info.annotation) or (
        info.is_required() and info.default is PydanticUndefined
    )
