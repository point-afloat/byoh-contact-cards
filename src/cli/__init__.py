# src/cli/__init__.py

"""Contact Card: a small tool for extracting contact info from scanned/handwritten cards.
Run `uv run contact-card` to launch the review UI.
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launches the contact card review UI in Streamlit."""
    review_app = Path(__file__).parent.parent / "review" / "app.py"
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(review_app)],
            check=False,
        )
    except KeyboardInterrupt:
        pass
