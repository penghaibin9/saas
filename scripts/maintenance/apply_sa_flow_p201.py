from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    raise RuntimeError('temporary blob should be restored by unified construction gate')


if __name__ == '__main__':
    main()
