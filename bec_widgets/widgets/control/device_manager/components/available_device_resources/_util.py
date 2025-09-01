from typing import Any, Callable, Generator, Iterable, TypeVar

_T = TypeVar("_T")
_RT = TypeVar("_RT")


def yield_only_passing(fn: Callable[[_T], _RT], vals: Iterable[_T]) -> Generator[_RT, Any, None]:
    for v in vals:
        try:
            yield fn(v)
        except BaseException:
            pass
