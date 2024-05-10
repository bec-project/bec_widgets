from bec_lib.utils.import_utils import lazy_import_from

# from .auto_updates import AutoUpdates, ScanInfo
# TODO: put back when Pydantic gets faster
AutoUpdates, ScanInfo = lazy_import_from(
    "bec_widgets.cli.auto_updates", ("AutoUpdates", "ScanInfo")
)
from .client import BECDockArea, BECFigure
