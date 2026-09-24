"""Application entry point: python -m sentin_harden

The import is absolute on purpose. Freezing hands this file to the runtime as
the starting script rather than as part of the package, and a relative import
has nothing to reach back to at that point. Absolute works both ways.
"""

import sys

from sentin_harden.ui import main

if __name__ == "__main__":
    sys.exit(main())
