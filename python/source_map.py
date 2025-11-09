from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _normalize_path_string(value: str) -> str:
    """Normalize a filesystem path string to POSIX form."""
    if value is None:
        return ""
    if value == "":
        return ""
    return Path(value).as_posix()


def _parse_prefix_map(mapping: Optional[str]) -> Dict[str, str]:
    """
    Parse a clang-style prefix map string (\"old=new\").
    Returns a dict keyed by the remapped prefix (new) with values of the original (old).
    """
    if not mapping:
        return {}
    parts = mapping.split(":")
    result: Dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        old, new = part.split("=", 1)
        if old == "":
            continue
        result[_normalize_path_string(new) or "."] = _normalize_path_string(old)
    return result


class SourceMap:
    """
    Helper for resolving source file paths using build/debug metadata.

    The structure aligns with docs/sources_json.md.
    """

    def __init__(
        self,
        *,
        project_root: Path,
        prefix_map: Optional[str],
        sources: Iterable[Dict[str, str]],
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.prefix_map = _parse_prefix_map(prefix_map)
        self.sources: List[Dict[str, str]] = list(sources)
        self._index: Dict[str, List[Dict[str, str]]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for entry in self.sources:
            candidates = set()
            for key in ("file", "relative", "path"):
                value = entry.get(key)
                if not value:
                    continue
                norm = _normalize_path_string(value)
                if norm:
                    candidates.add(norm)
                    if norm.startswith("./"):
                        candidates.add(norm[2:])
            path_value = entry.get("path")
            if path_value:
                norm_path = _normalize_path_string(path_value)
                for new_prefix, old_prefix in self.prefix_map.items():
                    if norm_path.startswith(old_prefix):
                        remapped = new_prefix.rstrip("/") + norm_path[len(old_prefix) :]
                        candidates.add(_normalize_path_string(remapped))
            for key in candidates:
                self._index.setdefault(key, []).append(entry)

    @classmethod
    def from_file(cls, sources_json: Path) -> "SourceMap":
        data = json.loads(Path(sources_json).read_text(encoding="utf-8"))
        return cls(
            project_root=Path(data.get("project_root", ".")),
            prefix_map=data.get("prefix_map"),
            sources=data.get("sources", []),
        )

    def resolve(
        self,
        requested: str | Path,
        *,
        search_roots: Optional[Iterable[Path]] = None,
    ) -> Path:
        """
        Resolve a requested path to an actual filesystem location.
        Raises FileNotFoundError when no suitable match is found.
        """
        raw = _normalize_path_string(str(requested))
        if not raw:
            raise FileNotFoundError("Empty path cannot be resolved")

        lookup_keys = {raw}
        if raw.startswith("./"):
            lookup_keys.add(raw[2:])
        if not raw.startswith("/"):
            lookup_keys.add(_normalize_path_string(self.project_root / raw))
        for new_prefix, old_prefix in self.prefix_map.items():
            if raw.startswith(new_prefix):
                rewritten = old_prefix.rstrip("/") + raw[len(new_prefix) :]
                lookup_keys.add(_normalize_path_string(rewritten))

        candidates = []
        for key in lookup_keys:
            matches = self._index.get(key)
            if matches:
                candidates.extend(matches)

        if not candidates:
            raise FileNotFoundError(requested)

        search_roots_list = [self.project_root]
        if search_roots:
            search_roots_list.extend(Path(root).resolve() for root in search_roots)
        search_roots_list.append(Path.cwd())

        for entry in candidates:
            direct_path = entry.get("path")
            if direct_path:
                resolved_direct = Path(direct_path)
                if resolved_direct.exists():
                    return resolved_direct
            rel_field = entry.get("file") or entry.get("relative")
            if rel_field:
                rel_clean = rel_field.lstrip("./")
                for root in search_roots_list:
                    candidate = root / rel_clean
                    if candidate.exists():
                        return candidate

        entry = candidates[0]
        fallback = entry.get("path") or entry.get("file") or entry.get("relative")
        if not fallback:
            raise FileNotFoundError(requested)
        return Path(fallback)

    def entries(self) -> List[Dict[str, str]]:
        return list(self.sources)
