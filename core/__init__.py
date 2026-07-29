"""CloudMount core — hosts, mounts, keychain, rclone."""

def _read_version() -> str:
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parent.parent / "VERSION"
        if p.is_file():
            return p.read_text().strip() or "0.0.1"
    except Exception:
        pass
    return "0.0.1"


__version__ = _read_version()
APP_NAME = "CloudMount"
SERVICE = "com.youramaryllis.cloudmount"
