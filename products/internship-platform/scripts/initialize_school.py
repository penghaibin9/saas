"""Local entry point for the same initializer included in the standalone image."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.initialize_school import initialize, main

if __name__ == '__main__':
    main()
