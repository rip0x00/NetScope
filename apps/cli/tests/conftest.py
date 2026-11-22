import sys
from pathlib import Path

# Make the CLI package importable without installation, the same way
# the core test suite does. netscope_core itself comes from the
# editable install in the repository venv.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
