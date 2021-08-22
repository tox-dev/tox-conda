import json
from datetime import datetime, timedelta
from typing import Any, Optional

from platformdirs import user_cache_path

from .version import version_tuple


class Cache:
    def __init__(self) -> None:
        version = ".".join(str(i) for i in version_tuple[0:3])
        self._path = user_cache_path(appname="conda", version=version) / "conda-info.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            value = json.loads(self._path.read_text())
        except (ValueError, OSError):
            value = {}
        self._content = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self._path})"

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._content, indent=2))

    def get_ttl_value(self, section: str, sub_section: Optional[str] = None, version: int = 1) -> Optional[Any]:
        if section in self._content:
            value = self._content[section]
            if sub_section is not None:
                if isinstance(value, dict) and sub_section in value:
                    value = value[sub_section]
                else:
                    value = None
        else:
            value = None
        if value is not None:
            until = datetime.fromisoformat(value["until"])
            if datetime.now() < until and value.get("version", 0) == version:
                return value["value"]
        return None

    def set_ttl_value(
        self, value: object, version: int, ttl: timedelta, section: str, sub_section: Optional[str] = None
    ) -> None:
        content = {"version": version, "until": (datetime.now() + ttl).isoformat(), "value": value}
        if sub_section is None:
            self._content[section] = content
        else:
            if self._content.get(section) is None:
                self._content[section] = {sub_section: content}
            else:
                self._content[section][sub_section] = content
        self._write()


__all__ = [
    "Cache",
]
