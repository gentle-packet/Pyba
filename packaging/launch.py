"""PyInstaller entry point — absolute imports only (pyba.ui.__main__ is relative)."""

import sys

from pyba.ui.app import main

sys.exit(main())
