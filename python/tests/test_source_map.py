import json
import shutil
from pathlib import Path

import pytest

from python.source_map import SourceMap


def make_sources_json(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_resolve_current_root(tmp_path):
    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    source_file = src_dir / "main.c"
    source_file.write_text("int main(){return 0;}", encoding="utf-8")
    data = {
        "version": 1,
        "project_root": str(project_root),
        "prefix_map": f"{project_root}=.",
        "sources": [
            {
                "file": "src/main.c",
                "path": str(source_file),
                "relative": "./src/main.c",
            }
        ],
    }
    smap = SourceMap.from_file(make_sources_json(tmp_path, data))

    assert smap.resolve("./src/main.c") == source_file
    assert smap.resolve("src/main.c") == source_file
    assert smap.resolve(str(source_file)) == source_file


def test_resolve_in_relocated_project(tmp_path):
    old_root = tmp_path / "old_project"
    new_root = tmp_path / "new_project"
    src_rel = Path("engine") / "core.c"
    (old_root / "engine").mkdir(parents=True)
    (new_root / "engine").mkdir(parents=True)
    old_file = old_root / src_rel
    new_file = new_root / src_rel
    old_file.write_text("int core(){return 1;}", encoding="utf-8")
    shutil.copy2(old_file, new_file)
    old_file.unlink()

    data = {
        "version": 1,
        "project_root": str(old_root),
        "prefix_map": f"{old_root}=.",
        "sources": [
            {
                "file": "engine/core.c",
                "path": str(old_file),
                "relative": "./engine/core.c",
            }
        ],
    }
    smap = SourceMap.from_file(make_sources_json(tmp_path, data))

    resolved = smap.resolve("./engine/core.c", search_roots=[new_root])
    assert resolved == new_file


def test_resolve_missing_should_raise(tmp_path):
    project_root = tmp_path / "root"
    project_root.mkdir()
    data = {
        "version": 1,
        "project_root": str(project_root),
        "sources": [],
    }
    smap = SourceMap.from_file(make_sources_json(tmp_path, data))
    with pytest.raises(FileNotFoundError):
        smap.resolve("missing.c")


def test_resolve_symlink(tmp_path):
    old_root = tmp_path / "app"
    new_root = tmp_path / "relocated"
    (new_root / "src").mkdir(parents=True)
    shared_target = tmp_path / "shared" / "module.c"
    shared_target.parent.mkdir(parents=True)
    shared_target.write_text("int module(){return 42;}", encoding="utf-8")
    relocated = new_root / "src" / "module.c"
    try:
        relocated.symlink_to(shared_target)
    except (OSError, NotImplementedError) as exc:  # Windows may lack symlink privilege
        pytest.skip(f"symlink not supported in this environment: {exc}")
    original = old_root / "src" / "module.c"
    data = {
        "version": 1,
        "project_root": str(old_root),
        "prefix_map": f"{old_root}=.",
        "sources": [
            {
                "file": "src/module.c",
                "path": str(original),
                "relative": "./src/module.c",
            }
        ],
    }
    smap = SourceMap.from_file(make_sources_json(tmp_path, data))
    resolved = smap.resolve("./src/module.c", search_roots=[new_root])
    assert resolved == relocated


def test_prefix_map_reverse_lookup(tmp_path):
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    file_path = project_root / "module.c"
    file_path.write_text("int module(){return 2;}", encoding="utf-8")
    data = {
        "version": 1,
        "project_root": str(project_root),
        "prefix_map": f"{project_root}=.",
        "sources": [
            {
                "path": str(file_path),
            }
        ],
    }
    smap = SourceMap.from_file(make_sources_json(tmp_path, data))
    assert smap.resolve("module.c") == file_path
