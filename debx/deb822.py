from collections import OrderedDict
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, MutableMapping, Union


class Deb822(MutableMapping[str, Any]):
    def __init__(self, data: Mapping[str, Any] = MappingProxyType({})) -> None:
        self.fields: OrderedDict[str, Any] = OrderedDict()
        if not data:
            return

        for k, v in data.items():
            self.fields[k] = v

    @classmethod
    def parse(cls, text: str) -> "Deb822":
        inst = cls()
        current = None
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            if ":" in line and not line.startswith(" "):
                key, val = line.split(":", 1)
                inst.fields[key.strip()] = val.lstrip()
                current = key.strip()
            elif line.startswith(" ") and current:
                inst.fields[current] += "\n" + line.lstrip()
        return inst

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Deb822":
        path = Path(path)
        return cls.parse(path.read_text())

    def dump(self) -> str:
        lines = []
        for key, val in self.fields.items():
            if "\n" in val:
                parts = val.split("\n")
                lines.append(f"{key}: {parts[0]}")
                for cont in parts[1:]:
                    lines.append(f" {cont}")
            else:
                lines.append(f"{key}: {val}")
        return "\n".join(lines) + "\n"

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.fields)

    def __setitem__(self, key, value):
        self.fields[key] = value

    def __delitem__(self, key):
        del self.fields[key]

    def __getitem__(self, key):
        return self.fields[key]

    def __len__(self):
        return len(self.fields)

    def __iter__(self):
        return iter(self.fields)
