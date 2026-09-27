"""Make the standalone benchmark package importable from repository-root tests."""

import sys
from pathlib import Path


SIMULATION_ROOT = Path(__file__).parents[2]
if str(SIMULATION_ROOT) not in sys.path:
    sys.path.insert(0, str(SIMULATION_ROOT))
