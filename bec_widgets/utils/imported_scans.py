"""
Scans opened from files that BEC wrote, but that are not in the scan history of the session.

Such a scan is served like a scan of the history, from its file, under the id
``imported:<path>``: the Data API reads it through :class:`ImportedFileDataPath`, and a
Waveform finds it with :func:`imported_scan_item` where it would look in the history.
Nothing is written to the history and nothing is kept across restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bec_lib.data_api.paths.file import FileDataPath
from bec_lib.data_api.scenarios import Scenario
from bec_lib.logger import bec_logger
from bec_lib.scan_data_container import ScanDataContainer

logger = bec_logger.logger

#: Start of the id of an imported scan; the path of its file follows.
IMPORTED_PREFIX = "imported:"
#: The data source of the imported scans in the Data API.
IMPORTED_SOURCE = "imported_file"


def imported_id(file_path: str) -> str:
    """
    The id an imported scan is known by.

    Args:
        file_path (str): Path of its file.

    Returns:
        str: ``imported:<path>``.
    """
    return f"{IMPORTED_PREFIX}{file_path}"


def is_imported(scan_id: str | None) -> bool:
    """Whether a scan id names an imported scan."""
    return isinstance(scan_id, str) and scan_id.startswith(IMPORTED_PREFIX)


@dataclass
class ImportedScan:
    """
    The catalog entry of an imported scan, with the attributes of a scan history message
    that the Data API and the plots read.
    """

    scan_id: str
    file_path: str
    #: The scan id the file itself names.
    file_scan_id: str = ""
    scan_number: int | None = None
    dataset_number: int | None = None
    scan_name: str = ""
    exit_status: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    num_points: int | None = None
    num_monitored_readouts: int | None = None
    stored_data_info: dict = field(default_factory=dict)
    request_inputs: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class ImportedScanItem(ScanDataContainer):
    """The stored data of an imported scan, read from its file, under the imported id."""

    def __init__(self, scan: ImportedScan):
        super().__init__(file_path=scan.file_path)
        self._msg = scan

    def _load_metadata(self) -> None:
        if self._loaded_metadata:
            return
        super()._load_metadata()
        bec = self.metadata.get("bec")
        if isinstance(bec, dict):
            # Known by the imported id, as the plots ask for it, not by the file's own.
            bec["scan_id"] = self._msg.scan_id


class ImportedFileDataPath(FileDataPath):
    """Serves the imported scans from their files, as the file path serves the history."""

    data_source = IMPORTED_SOURCE
    priority = 40

    def __init__(self, client, lock=None):
        super().__init__(client, lock)
        self._scans: dict[str, ImportedScan] = {}

    def add(self, scan: ImportedScan) -> None:
        """Serve an imported scan."""
        with self._lock:
            self._scans[scan.scan_id] = scan

    def discard(self, scan_id: str) -> None:
        """Serve an imported scan no more."""
        with self._lock:
            self._scans.pop(scan_id, None)

    def scan(self, scan_id: str) -> ImportedScan | None:
        """The imported scan of an id, or None."""
        return self._scans.get(scan_id)

    def catalog_entry(self, scan_id: str) -> ImportedScan | None:
        return self._scans.get(scan_id)

    def describe_scan(self, scan_id: str) -> Scenario | None:
        return Scenario.CLOSED_SCAN if scan_id in self._scans else None

    def _load_container(self, request, msg):  # pylint: disable=unused-argument
        return ImportedScanItem(msg)


def _data_api(client) -> Any:
    try:
        return getattr(client, "data_api", None)
    except Exception:  # pylint: disable=broad-except
        return None


def _path(client, create: bool = False) -> ImportedFileDataPath | None:
    """The imported scans' data path of a client's Data API, registered when asked."""
    api = _data_api(client)
    paths = getattr(api, "paths", None)
    if not isinstance(paths, list):
        return None
    path = next((p for p in paths if isinstance(p, ImportedFileDataPath)), None)
    if path is None and create:
        path = ImportedFileDataPath(client)
        try:
            api.register_path(path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Imported scans cannot be read through the Data API: {exc}")
            return None
    return path


def register_imported(client, scan: ImportedScan) -> None:
    """
    Make an imported scan readable for the Data API and the plots of a client.

    Args:
        client: The BEC client.
        scan (ImportedScan): The scan.
    """
    path = _path(client, create=True)
    if path is not None:
        path.add(scan)


def forget_imported(client, scan_id: str) -> None:
    """
    Let an imported scan go.

    Args:
        client: The BEC client.
        scan_id (str): Its imported id.
    """
    path = _path(client)
    if path is not None:
        path.discard(scan_id)


def imported_scan_item(client, scan_id: str | None) -> ImportedScanItem | None:
    """
    The stored data of an imported scan, as the history gives that of a scan of its own.

    Args:
        client: The BEC client.
        scan_id (str | None): The scan id.

    Returns:
        ImportedScanItem | None: The scan's data, or None for a scan that is not imported.
    """
    if not is_imported(scan_id):
        return None
    path = _path(client)
    scan = path.scan(scan_id) if path is not None else None
    return ImportedScanItem(scan) if scan is not None else None
