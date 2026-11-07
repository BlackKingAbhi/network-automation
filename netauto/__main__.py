"""Allows the tool to be run as:  python -m netauto <command>"""

import sys

from netauto.main import main

if __name__ == "__main__":
    sys.exit(main())
