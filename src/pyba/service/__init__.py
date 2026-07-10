"""Service layer: the only Pyba layer with side effects (disk, network).

Orchestrates engine (deadlock-eos) + port + persistence for the desktop UI:
game-data loading, the fit library, shareable build codes, and item
win/usage annotations.
"""

from .analytics import ItemAnalytics, ItemStat
from .codes import decode_fit, encode_fit, import_any
from .data import find_dumps_dir, latest_build_dir, load_game_data
from .fitstore import FitInfo, FitStore, slugify
from .update import app_dumps_dir, check_for_update, download_update, revert_to_bundled

__all__ = [
    "load_game_data", "find_dumps_dir", "latest_build_dir",
    "FitStore", "FitInfo", "slugify",
    "encode_fit", "decode_fit", "import_any",
    "ItemAnalytics", "ItemStat",
    "app_dumps_dir", "check_for_update", "download_update", "revert_to_bundled",
]
