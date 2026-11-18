"""
Read-only access to HDF5 files that never keeps a file open.

Every function here opens the file, reads one piece and closes it again. Files are opened
without taking the HDF5 file lock, so a reader can never stop another program from opening
the file for writing. Nothing reads a whole dataset: callers ask for a listing of one group,
one frame, a range of rows or a reduced overview.

The module has no Qt dependency. It is called from worker threads by
:class:`~bec_widgets.widgets.services.hdf5_viewer.h5_service.H5Service`.
"""

from __future__ import annotations

import contextlib
import math
import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import h5py
import numpy as np

#: A file changed less than this many seconds ago is treated as possibly still being written.
RECENT_WRITE_SECONDS = 5.0
#: Points of a reduced curve: the smallest and the largest sample of every bin of rows.
OVERVIEW_POINTS = 200_000
#: Elements read from the file in one step while a long signal is reduced.
SLAB_ELEMENTS = 4_000_000
#: Pixels of one frame that are read as they are; larger frames are read with a stride.
MAX_FRAME_PIXELS = 16_000_000
#: Attributes listed for one node, and characters shown of one attribute value.
MAX_ATTRIBUTES = 200
MAX_ATTRIBUTE_CHARS = 400
#: Suffixes offered when a scan folder is listed.
HDF5_SUFFIXES = (".h5", ".hdf5", ".hdf", ".nxs", ".nx", ".nexus")

NodeKind = Literal["file", "group", "dataset", "link", "broken", "other"]
ErrorKind = Literal["missing", "busy", "denied", "unreadable", "cancelled"]

CancelCheck = Callable[[], bool]
ProgressCallback = Callable[[float], None]


class H5ReadError(Exception):
    """A read that could not be served, with a text that can be shown as it is."""

    def __init__(self, message: str, kind: ErrorKind = "unreadable", file_path: str = ""):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.file_path = file_path


@dataclass(frozen=True)
class H5Node:
    """One entry of a group listing. Describes the node without holding it."""

    name: str
    path: str
    file_path: str
    kind: NodeKind
    shape: tuple[int, ...] | None = None
    dtype: str = ""
    dtype_kind: str = ""
    n_children: int | None = None
    nx_class: str = ""
    units: str = ""
    link_file: str = ""
    link_path: str = ""
    is_default: bool = False

    @property
    def size(self) -> int:
        """Number of elements of a dataset, 0 for everything else."""
        if self.kind != "dataset" or self.shape is None:
            return 0
        return int(math.prod(self.shape))

    @property
    def ndim(self) -> int:
        """Number of dimensions of a dataset."""
        return len(self.shape) if self.shape is not None else 0

    @property
    def is_numeric(self) -> bool:
        """Whether the values can be drawn as numbers."""
        return self.dtype_kind in ("i", "u", "f", "b")

    @property
    def is_container(self) -> bool:
        """Whether the node can have children in the tree."""
        return self.kind in ("file", "group", "link")


@dataclass(frozen=True)
class AxisCandidate:
    """A dataset that can serve as the x axis of another one."""

    name: str
    path: str
    file_path: str
    units: str = ""
    preferred: bool = False


@dataclass(frozen=True)
class H5Details:
    """Everything the details pane shows about one node."""

    node: H5Node
    attributes: dict[str, str] = field(default_factory=dict)
    chunks: tuple[int, ...] | None = None
    compression: str = ""
    logical_bytes: int = 0
    stored_bytes: int = 0
    x_candidates: tuple[AxisCandidate, ...] = ()


@dataclass(frozen=True)
class FileSummary:
    """What is known about a file without opening it."""

    file_path: str
    size_bytes: int
    modified: float
    recently_modified: bool
    held_by_writer: bool = False

    @property
    def busy(self) -> bool:
        """Whether the file looks like it is still being written."""
        return self.recently_modified or self.held_by_writer


@dataclass(frozen=True)
class CurveData:
    """Rows of a 1D signal, whole or reduced to the extremes of bins of rows."""

    x: np.ndarray
    y: np.ndarray
    start: int
    stop: int
    total: int
    reduced: bool
    bytes_read: int


@dataclass(frozen=True)
class FrameData:
    """One 2D frame of a dataset, read with ``stride`` when it is very large."""

    data: np.ndarray
    stride: int
    bytes_read: int


@dataclass(frozen=True)
class TableData:
    """A window of rows and columns as display texts."""

    cells: list[list[str]]
    row_start: int
    col_start: int
    bytes_read: int


################################################################################
# Opening
################################################################################


def held_by_writer(file_path: str, lock_table: str = "/proc/locks") -> bool:
    """
    Tell whether a program on this computer holds a write lock on the file.

    The kernel's lock table is read; no lock is taken or tested. Where the table does not
    exist (macOS) or the writer runs on another computer, the answer is False and the
    modification time is the only sign of a writer.

    Args:
        file_path (str): Path of the file.
        lock_table (str): The kernel's lock table, for tests.

    Returns:
        bool: True when a write lock on the file is listed.
    """
    try:
        stat = os.stat(file_path)
        key = f"{os.major(stat.st_dev):02x}:{os.minor(stat.st_dev):02x}:{stat.st_ino}"
        with open(lock_table, encoding="utf-8") as table:
            return any("WRITE" in line and key in line.split() for line in table)
    except OSError:
        return False


def file_summary(file_path: str, now: float | None = None) -> FileSummary:
    """
    Describe a file from the file system alone, without opening it.

    Args:
        file_path (str): Path of the file.
        now (float | None): Current time, for tests. Defaults to ``time.time()``.

    Returns:
        FileSummary: Size, modification time and whether it changed moments ago.
    """
    try:
        stat = Path(file_path).stat()
    except FileNotFoundError as exc:
        raise H5ReadError(
            f"{Path(file_path).name} was moved or deleted", "missing", file_path
        ) from exc
    except PermissionError as exc:
        raise H5ReadError(
            f"No permission to read {Path(file_path).name}", "denied", file_path
        ) from exc
    now = time.time() if now is None else now
    return FileSummary(
        file_path=str(file_path),
        size_bytes=stat.st_size,
        modified=stat.st_mtime,
        recently_modified=(now - stat.st_mtime) < RECENT_WRITE_SECONDS,
        held_by_writer=held_by_writer(str(file_path)),
    )


def _open(file_path: str, swmr: bool = False) -> h5py.File:
    """Open ``file_path`` for reading without taking the HDF5 file lock."""
    kwargs: dict[str, Any] = {"swmr": True, "libver": "latest"} if swmr else {}
    try:
        return h5py.File(file_path, "r", locking=False, **kwargs)
    except (TypeError, ValueError):
        # An HDF5 library without the locking switch, or one that insists on a lock for
        # this mode. The file is then locked for the length of this one short read only.
        return h5py.File(file_path, "r", **kwargs)
    except OSError as exc:
        if "flag values don't match" not in str(exc):
            raise
        # Another reader of this process holds the file open with the default lock, e.g.
        # the DataAPI reading a history curve. HDF5 refuses a second open with other
        # locking flags; one with the same flags joins that open and takes no lock of its own.
        return h5py.File(file_path, "r", **kwargs)


@contextlib.contextmanager
def open_readonly(file_path: str) -> Iterator[h5py.File]:
    """
    Open a file for one short read and close it again.

    No file lock is taken. A file that a writer keeps open in the mode made for
    simultaneous reading (SWMR) is opened in that mode. A file that is held by a writer
    in any other way is reported as busy and is not read.

    Args:
        file_path (str): Path of the file.

    Yields:
        h5py.File: The open file. It is closed when the block is left.
    """
    path = Path(file_path)
    if not path.exists():
        raise H5ReadError(f"{path.name} was moved or deleted", "missing", str(file_path))
    handle = None
    try:
        try:
            handle = _open(str(path))
        except OSError as exc:
            text = str(exc).lower()
            if "already open for write" in text or "unable to lock file" in text:
                try:
                    handle = _open(str(path), swmr=True)
                except OSError as swmr_exc:
                    raise H5ReadError(
                        f"{path.name} is being written by another program", "busy", str(file_path)
                    ) from swmr_exc
            elif "permission denied" in text:
                raise H5ReadError(
                    f"No permission to read {path.name}", "denied", str(file_path)
                ) from exc
            else:
                raise H5ReadError(
                    f"{path.name} is not a readable HDF5 file", "unreadable", str(file_path)
                ) from exc
        yield handle
    finally:
        if handle is not None:
            with contextlib.suppress(Exception):
                handle.close()


@contextlib.contextmanager
def _guarded(file_path: str, action: str) -> Iterator[None]:
    """Turn the library errors of one read into :class:`H5ReadError`."""
    try:
        yield
    except H5ReadError as exc:
        exc.file_path = exc.file_path or file_path
        raise
    except KeyError as exc:
        raise H5ReadError(
            f"{action}: not found in {Path(file_path).name}", "missing", file_path
        ) from exc
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise H5ReadError(f"{action}: {exc}", "unreadable", file_path) from exc


################################################################################
# Listing and describing
################################################################################


def _text(value: Any) -> str:
    """Display text of an attribute or a scalar."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray):
        if value.dtype.kind in ("S", "O", "U"):
            flat = [_text(item) for item in value.ravel().tolist()]
            return flat[0] if value.ndim == 0 or value.size == 1 else ", ".join(flat)
        if value.size == 1:
            return _text(value.ravel()[0])
        return np.array2string(value, threshold=12, edgeitems=3, separator=", ")
    if isinstance(value, np.generic):
        if value.dtype.kind == "f":
            return f"{float(value):.10g}"
        return str(value.item())
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def _attr_text(attrs: Any, name: str) -> str:
    """One attribute as text, empty when it is missing or unreadable."""
    try:
        if name not in attrs:
            return ""
        return _text(attrs[name])
    except Exception:  # pylint: disable=broad-except
        return ""


def _dtype_name(dtype: np.dtype) -> tuple[str, str]:
    """Readable name and numpy kind of a stored type."""
    if h5py.check_string_dtype(dtype) is not None:
        return "string", "S"
    vlen = h5py.check_vlen_dtype(dtype)
    if vlen is not None:
        return f"{np.dtype(vlen).name}[]", "O"
    if dtype.names:
        return "compound", "V"
    return dtype.name, dtype.kind


def _node_of(obj: Any, name: str, path: str, file_path: str, is_default: bool = False) -> H5Node:
    """Describe an opened group or dataset."""
    if isinstance(obj, h5py.Dataset):
        dtype, kind = _dtype_name(obj.dtype)
        return H5Node(
            name=name,
            path=path,
            file_path=file_path,
            kind="dataset",
            shape=tuple(int(n) for n in obj.shape) if obj.shape is not None else (),
            dtype=dtype,
            dtype_kind=kind,
            units=_attr_text(obj.attrs, "units"),
            is_default=is_default,
        )
    if isinstance(obj, h5py.Group):
        return H5Node(
            name=name,
            path=path,
            file_path=file_path,
            kind="group",
            n_children=len(obj),
            nx_class=_attr_text(obj.attrs, "NX_class"),
            is_default=is_default,
        )
    return H5Node(name=name, path=path, file_path=file_path, kind="other")


def _join(parent: str, name: str) -> str:
    return f"/{name}" if parent in ("", "/") else f"{parent.rstrip('/')}/{name}"


def resolve_link_file(file_path: str, link_file: str) -> str:
    """
    Path of the file an external link points to.

    Args:
        file_path (str): The file that holds the link.
        link_file (str): File name stored in the link, absolute or relative to that file.

    Returns:
        str: The target file path.
    """
    target = Path(link_file)
    if not target.is_absolute():
        target = Path(file_path).parent / target
    return str(target)


def list_children(file_path: str, group_path: str = "/") -> list[H5Node]:
    """
    List the direct children of one group.

    Links into other files are reported as links and are not followed, so listing a group
    never opens a second file.

    Args:
        file_path (str): Path of the file.
        group_path (str): Path of the group inside the file.

    Returns:
        list[H5Node]: One node per child, in the order of the file.
    """
    nodes: list[H5Node] = []
    with open_readonly(file_path) as handle, _guarded(file_path, f"Listing {group_path}"):
        group = handle[group_path] if group_path not in ("", "/") else handle
        if not isinstance(group, h5py.Group):
            return nodes
        default = _attr_text(group.attrs, "default") or _attr_text(group.attrs, "signal")
        for name in group:
            path = _join(group_path, name)
            link = group.get(name, getlink=True)
            if isinstance(link, h5py.ExternalLink):
                nodes.append(
                    H5Node(
                        name=name,
                        path=path,
                        file_path=file_path,
                        kind="link",
                        link_file=resolve_link_file(file_path, link.filename),
                        link_path=link.path,
                    )
                )
                continue
            try:
                obj = group.get(name)
            except Exception:  # pylint: disable=broad-except
                obj = None
            if obj is None:
                nodes.append(H5Node(name=name, path=path, file_path=file_path, kind="broken"))
                continue
            nodes.append(_node_of(obj, name, path, file_path, is_default=name == default))
    return nodes


def scan_folder_files(file_path: str, limit: int = 24) -> list[FileSummary]:
    """
    List the HDF5 files that belong to a scan file, the file itself first.

    The files of one scan start with the same name: next to ``S00412_master.h5`` that is
    every HDF5 file whose name starts with ``S00412_``. No file is opened.

    Args:
        file_path (str): Path of the scan's main file.
        limit (int): Largest number of further files listed.

    Returns:
        list[FileSummary]: The main file and the files that belong to it.
    """
    main = Path(file_path)
    out = [file_summary(str(main))]
    if "_" not in main.stem:
        return out
    prefix = f"{main.stem.rsplit('_', 1)[0]}_"
    try:
        neighbours = sorted(
            entry
            for entry in main.parent.iterdir()
            if entry.name.startswith(prefix)
            and entry.suffix.lower() in HDF5_SUFFIXES
            and entry != main
            and entry.is_file()
        )
    except OSError:
        neighbours = []
    for entry in neighbours[:limit]:
        with contextlib.suppress(H5ReadError):
            out.append(file_summary(str(entry)))
    return out


def _compression_text(dset: h5py.Dataset) -> str:
    if dset.compression:
        opts = dset.compression_opts
        return f"{dset.compression}" + (f" ({opts})" if opts not in (None, ()) else "")
    with contextlib.suppress(Exception):
        plist = dset.id.get_create_plist()
        if plist.get_nfilters():
            return "filter " + ", ".join(
                str(plist.get_filter(index)[0]) for index in range(plist.get_nfilters())
            )
    return ""


def _x_candidates(dset: h5py.Dataset, file_path: str, limit: int = 40) -> tuple[AxisCandidate, ...]:
    """1D numeric siblings of ``dset`` with as many rows as its plotted axis."""
    parent = dset.parent
    if dset.ndim < 1 or dset.shape[-1] < 2:
        return ()
    length = dset.shape[-1] if dset.ndim > 1 else dset.shape[0]
    preferred = ""
    axes = parent.attrs.get("axes") if "axes" in parent.attrs else None
    if axes is not None:
        names = [_text(item) for item in np.atleast_1d(axes).ravel().tolist()]
        preferred = names[-1] if names else ""
    out: list[AxisCandidate] = []
    own = dset.name.rsplit("/", 1)[-1]
    for name in parent:
        if len(out) >= limit:
            break
        if name == own:
            continue
        link = parent.get(name, getlink=True)
        if isinstance(link, h5py.ExternalLink):
            continue
        with contextlib.suppress(Exception):
            sibling = parent.get(name)
            if (
                isinstance(sibling, h5py.Dataset)
                and sibling.ndim == 1
                and sibling.shape[0] == length
                and sibling.dtype.kind in ("i", "u", "f")
            ):
                out.append(
                    AxisCandidate(
                        name=name,
                        path=_join(parent.name, name),
                        file_path=file_path,
                        units=_attr_text(sibling.attrs, "units"),
                        preferred=name == preferred,
                    )
                )
    return tuple(sorted(out, key=lambda item: not item.preferred))


def describe(file_path: str, path: str = "/") -> H5Details:
    """
    Describe one node: its attributes and, for a dataset, how it is stored.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the node inside the file.

    Returns:
        H5Details: The description. No dataset values are read.
    """
    with open_readonly(file_path) as handle, _guarded(file_path, f"Reading {path}"):
        obj = handle[path] if path not in ("", "/") else handle
        name = path.rstrip("/").rsplit("/", 1)[-1] or Path(file_path).name
        node = _node_of(obj, name, path or "/", file_path)
        attributes: dict[str, str] = {}
        for index, key in enumerate(obj.attrs):
            if index >= MAX_ATTRIBUTES:
                break
            text = _attr_text(obj.attrs, key)
            attributes[key] = (
                text if len(text) <= MAX_ATTRIBUTE_CHARS else text[:MAX_ATTRIBUTE_CHARS] + "…"
            )
        if not isinstance(obj, h5py.Dataset):
            return H5Details(node=node, attributes=attributes)
        return H5Details(
            node=node,
            attributes=attributes,
            chunks=tuple(obj.chunks) if obj.chunks else None,
            compression=_compression_text(obj),
            logical_bytes=int(obj.size) * int(obj.dtype.itemsize),
            stored_bytes=int(obj.id.get_storage_size()),
            x_candidates=_x_candidates(obj, file_path) if node.is_numeric else (),
        )


def resolve_link(node: H5Node) -> H5Node:
    """
    Describe the target of an external link. This is the only place a second file is opened.

    Args:
        node (H5Node): A node of kind ``link``.

    Returns:
        H5Node: The target as a group or dataset of the linked file, keeping the link's name.
    """
    if node.kind != "link":
        return node
    with (
        open_readonly(node.link_file) as handle,
        _guarded(node.link_file, f"Following the link {node.name}"),
    ):
        obj = handle[node.link_path]
        target = _node_of(obj, node.name, node.link_path, node.link_file)
    return target


def find_nodes(
    file_path: str, text: str, limit: int = 200, cancel: CancelCheck | None = None
) -> list[H5Node]:
    """
    Find groups and datasets whose name contains ``text``.

    Only names are compared, in the order of the file. Links into other files are not
    followed. The search stops at ``limit`` matches or when ``cancel`` says so.

    Args:
        file_path (str): Path of the file.
        text (str): Text to look for, case-insensitive.
        limit (int): Largest number of matches returned.
        cancel (CancelCheck | None): Returns True when the search is no longer wanted.

    Returns:
        list[H5Node]: The matching nodes.
    """
    needle = text.strip().lower()
    matches: list[H5Node] = []
    if not needle:
        return matches
    with open_readonly(file_path) as handle, _guarded(file_path, "Searching"):

        def _visit(name: str, obj: Any):
            if cancel is not None and cancel():
                return True
            leaf = name.rsplit("/", 1)[-1]
            if needle in leaf.lower():
                matches.append(_node_of(obj, leaf, f"/{name}", file_path))
                if len(matches) >= limit:
                    return True
            return None

        handle.visititems(_visit)
    return matches


@dataclass(frozen=True)
class FoundBranches:
    """The entries whose name matches a search, and the groups that lead to them."""

    matches: tuple[H5Node, ...]
    #: The groups on the way to a match that do not match themselves, in no particular order.
    ancestors: tuple[H5Node, ...]
    #: Whether the search stopped at its limit, so that more matches may exist.
    truncated: bool


def find_branches(
    file_path: str, text: str, limit: int = 200, cancel: CancelCheck | None = None
) -> FoundBranches:
    """
    Find the entries whose own name contains ``text``, with the groups that lead to them.

    Only the last part of a path is compared, so the children of a matching group are not
    matches because of their parent. Links into other files are not followed.

    Args:
        file_path (str): Path of the file.
        text (str): Text to look for, case-insensitive.
        limit (int): Largest number of matches returned.
        cancel (CancelCheck | None): Returns True when the search is no longer wanted.

    Returns:
        FoundBranches: The matches in the order of the file and the groups above them.
    """
    matches = find_nodes(file_path, text, limit=limit, cancel=cancel)
    matched = {node.path for node in matches}
    wanted: list[str] = []
    for node in matches:
        parts = [part for part in node.path.split("/") if part][:-1]
        for depth in range(1, len(parts) + 1):
            path = "/" + "/".join(parts[:depth])
            if path not in matched and path not in wanted:
                wanted.append(path)
    ancestors: list[H5Node] = []
    if wanted:
        with open_readonly(file_path) as handle, _guarded(file_path, "Searching"):
            for path in wanted:
                if cancel is not None and cancel():
                    break
                ancestors.append(_node_of(handle[path], path.rsplit("/", 1)[-1], path, file_path))
    return FoundBranches(tuple(matches), tuple(ancestors), len(matches) >= limit)


################################################################################
# Reading values
################################################################################


def _dataset(handle: h5py.File, path: str) -> h5py.Dataset:
    obj = handle[path]
    if not isinstance(obj, h5py.Dataset):
        raise H5ReadError(f"{path} is not a dataset", "unreadable")
    return obj


def _check_index(dset: h5py.Dataset, index: tuple[int, ...], kept: int) -> tuple[int, ...]:
    """Validate the fixed leading indices of a read that keeps the last ``kept`` axes."""
    lead = dset.ndim - kept
    if lead < 0:
        raise H5ReadError(f"{dset.name} has too few dimensions for this view", "unreadable")
    index = tuple(int(i) for i in index)[:lead]
    index = index + (0,) * (lead - len(index))
    for axis, value in enumerate(index):
        if not 0 <= value < dset.shape[axis]:
            raise H5ReadError(
                f"Index {value} is outside dimension {axis} of {dset.name}", "unreadable"
            )
    return index


def read_curve(
    file_path: str,
    path: str,
    index: tuple[int, ...] = (),
    start: int | None = None,
    stop: int | None = None,
    max_points: int = OVERVIEW_POINTS,
    cancel: CancelCheck | None = None,
    progress: ProgressCallback | None = None,
    x_path: str | None = None,
) -> CurveData:
    """
    Read rows of a 1D signal, reduced when there are more than ``max_points``.

    The signal is the last axis of the dataset; ``index`` fixes the axes before it. A range
    with more rows than ``max_points`` is read block by block and reduced to the smallest
    and the largest sample of equally wide bins of rows, so peaks survive the reduction and
    only one block is in memory at a time.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the dataset inside the file.
        index (tuple[int, ...]): Position along the leading axes.
        start (int | None): First row. Defaults to the first row of the signal.
        stop (int | None): One past the last row. Defaults to the end.
        max_points (int): Largest number of points returned.
        cancel (CancelCheck | None): Returns True when the read is no longer wanted.
        progress (ProgressCallback | None): Called with the fraction read so far.
        x_path (str | None): Path of a 1D dataset of the same file with one x value per
            row. Without it the row numbers are the x values.

    Returns:
        CurveData: X values and values, and whether they were reduced.
    """
    with open_readonly(file_path) as handle, _guarded(file_path, f"Reading {path}"):
        dset = _dataset(handle, path)
        if dset.ndim == 0:
            value = np.atleast_1d(np.asarray(dset[()], dtype=float))
            return CurveData(np.zeros(1), value, 0, 1, 1, False, value.nbytes)
        lead = _check_index(dset, index, 1)
        total = int(dset.shape[-1])
        x_dset = None
        if x_path:
            x_dset = _dataset(handle, x_path)
            if x_dset.ndim != 1 or x_dset.shape[0] != total:
                raise H5ReadError(
                    f"{x_path} does not have one value per row of {path}", "unreadable"
                )
        first = 0 if start is None else max(0, min(int(start), total))
        last = total if stop is None else max(first, min(int(stop), total))
        rows = last - first
        if rows <= max_points:
            values = np.asarray(dset[lead + (slice(first, last),)])
            if x_dset is None:
                x_values = np.arange(first, last, dtype=np.float64)
                bytes_read = values.nbytes
            else:
                x_values = np.asarray(x_dset[first:last], dtype=np.float64)
                bytes_read = values.nbytes + x_values.nbytes
            return CurveData(
                x=x_values,
                y=values,
                start=first,
                stop=last,
                total=total,
                reduced=False,
                bytes_read=bytes_read,
            )
        bins = max(1, max_points // 2)
        bin_rows = math.ceil(rows / bins)
        bins = math.ceil(rows / bin_rows)
        lows = np.empty(bins, dtype=np.float64)
        highs = np.empty(bins, dtype=np.float64)
        x = np.empty(2 * bins, dtype=np.float64)
        block_bins = max(1, SLAB_ELEMENTS // bin_rows)
        bytes_read = 0
        for bin_start in range(0, bins, block_bins):
            if cancel is not None and cancel():
                raise H5ReadError("Read cancelled", "cancelled", file_path)
            bin_stop = min(bins, bin_start + block_bins)
            row_a = first + bin_start * bin_rows
            row_b = min(last, first + bin_stop * bin_rows)
            block = np.asarray(dset[lead + (slice(row_a, row_b),)])
            bytes_read += block.nbytes
            whole = (len(block) // bin_rows) * bin_rows
            if whole:
                shaped = block[:whole].reshape(-1, bin_rows)
                lows[bin_start : bin_start + len(shaped)] = np.fmin.reduce(shaped, axis=1)
                highs[bin_start : bin_start + len(shaped)] = np.fmax.reduce(shaped, axis=1)
            if whole < len(block):
                lows[bin_stop - 1] = np.fmin.reduce(block[whole:])
                highs[bin_stop - 1] = np.fmax.reduce(block[whole:])
            # Two x values per bin: at its first row and at its middle row.
            rows_a = np.arange(row_a, row_b, bin_rows)
            rows_b = np.minimum(rows_a + bin_rows // 2, row_b - 1)
            if x_dset is None:
                x[2 * bin_start : 2 * bin_stop : 2] = rows_a
                x[2 * bin_start + 1 : 2 * bin_stop : 2] = rows_b
            else:
                x_block = np.asarray(x_dset[row_a:row_b], dtype=np.float64)
                bytes_read += x_block.nbytes
                x[2 * bin_start : 2 * bin_stop : 2] = x_block[rows_a - row_a]
                x[2 * bin_start + 1 : 2 * bin_stop : 2] = x_block[rows_b - row_a]
            if progress is not None:
                progress(bin_stop / bins)
        y = np.empty(2 * bins, dtype=np.float64)
        y[0::2] = lows
        y[1::2] = highs
        return CurveData(
            x=x, y=y, start=first, stop=last, total=total, reduced=True, bytes_read=bytes_read
        )


def read_frame(
    file_path: str, path: str, index: tuple[int, ...] = (), max_pixels: int = MAX_FRAME_PIXELS
) -> FrameData:
    """
    Read one 2D frame: the last two axes of the dataset at ``index`` of the axes before.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the dataset inside the file.
        index (tuple[int, ...]): Position along the leading axes.
        max_pixels (int): A larger frame is read with a stride so that it stays below this.

    Returns:
        FrameData: The frame and the stride it was read with.
    """
    with open_readonly(file_path) as handle, _guarded(file_path, f"Reading {path}"):
        dset = _dataset(handle, path)
        lead = _check_index(dset, index, 2)
        height, width = int(dset.shape[-2]), int(dset.shape[-1])
        stride = max(1, math.ceil(math.sqrt(height * width / max(1, max_pixels))))
        data = np.asarray(dset[lead + (slice(None, None, stride), slice(None, None, stride))])
        return FrameData(data=data, stride=stride, bytes_read=data.nbytes)


def _cell_text(value: Any) -> str:
    if isinstance(value, (bytes, str, np.ndarray, np.generic, float)):
        return _text(value)
    return str(value)


def read_table(
    file_path: str,
    path: str,
    index: tuple[int, ...] = (),
    row_start: int = 0,
    row_stop: int = 100,
    col_start: int = 0,
    col_stop: int = 50,
) -> TableData:
    """
    Read a window of a dataset as texts for a table.

    A 1D dataset is one column, a dataset with more dimensions shows its last two axes at
    ``index`` of the axes before. A scalar is a single cell.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the dataset inside the file.
        index (tuple[int, ...]): Position along the leading axes.
        row_start (int): First row of the window.
        row_stop (int): One past the last row.
        col_start (int): First column of the window.
        col_stop (int): One past the last column.

    Returns:
        TableData: The cell texts of the window.
    """
    with open_readonly(file_path) as handle, _guarded(file_path, f"Reading {path}"):
        dset = _dataset(handle, path)
        if dset.ndim == 0:
            value = dset[()]
            return TableData([[_cell_text(value)]], 0, 0, int(dset.dtype.itemsize))
        if dset.ndim == 1:
            block = np.asarray(dset[row_start:row_stop]).reshape(-1, 1)
            col_start = 0
        else:
            lead = _check_index(dset, index, 2)
            block = np.asarray(
                dset[lead + (slice(row_start, row_stop), slice(col_start, col_stop))]
            )
        rows = block if block.dtype.kind in ("S", "O", "V") else block.tolist()
        cells = [[_cell_text(value) for value in row] for row in rows]
        return TableData(cells, row_start, col_start, int(block.nbytes))


def read_value(file_path: str, path: str, max_elements: int = 64) -> str:
    """
    Read a scalar or a very small dataset as text.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the dataset inside the file.
        max_elements (int): Datasets with more elements are refused.

    Returns:
        str: The value as text.
    """
    with open_readonly(file_path) as handle, _guarded(file_path, f"Reading {path}"):
        dset = _dataset(handle, path)
        if dset.size > max_elements:
            raise H5ReadError(f"{path} is too large to show as one value", "unreadable")
        return _text(np.asarray(dset[()]) if dset.ndim else dset[()])


def format_bytes(count: int | float) -> str:
    """
    Readable size.

    Args:
        count (int | float): Number of bytes.

    Returns:
        str: For example ``"9.9 MB"``.
    """
    value = float(count)
    for unit in ("bytes", "kB", "MB", "GB", "TB"):
        if value < 1000 or unit == "TB":
            return f"{int(value)} {unit}" if unit == "bytes" else f"{value:.3g} {unit}"
        value /= 1000
    return f"{value:.3g} TB"


def format_count(count: int) -> str:
    """
    Readable whole number, with thin spaces between the thousands.

    Args:
        count (int): The number.

    Returns:
        str: For example ``"1 200 000"``.
    """
    return f"{int(count):,}".replace(",", "\u2009")


def format_shape(shape: tuple[int, ...] | None) -> str:
    """
    Readable shape.

    Args:
        shape (tuple[int, ...] | None): Shape of a dataset.

    Returns:
        str: For example ``"600 × 1 679 × 1 475"``, or ``"scalar"``.
    """
    if shape is None:
        return ""
    if len(shape) == 0:
        return "scalar"
    return " × ".join(format_count(n) for n in shape)
