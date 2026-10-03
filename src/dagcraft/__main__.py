"""``python -m dagcraft pipeline.yaml``: the same as the ``dagcraft`` command.

Handy where the ``dagcraft`` script isn't on the PATH.
"""

import sys

from dagcraft.cli import main

if __name__ == "__main__":
    sys.exit(main())
