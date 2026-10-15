"""Tests of the Go engine (bin/ebengine.exe), driven through its JSON protocol.

Build it first with build_engine.bat.
"""

import json
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "bin" / ("ebengine.exe" if os.name == "nt" else "ebengine")

pytestmark = pytest.mark.skipif(not ENGINE.exists(), reason="engine not built")


def run(*args, lang="en"):
    out = subprocess.run([str(ENGINE), *args, "--lang", lang], stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, encoding="utf-8", timeout=60).stdout
    return [json.loads(line) for line in out.splitlines()]


def transfer(tmp_path, dest, mode="copy", layout="by_type", conflict="rename", files=(), dirs=()):
    job = tmp_path / "job.json"
    job.write_text(json.dumps({
        "dest": str(dest), "source_root": str(tmp_path / "src"), "mode": mode,
        "layout": layout, "conflict": conflict, "files": list(files), "dirs": list(dirs),
    }), encoding="utf-8")
    return run("transfer", "--job", str(job))


def tree(base):
    return sorted(p.relative_to(base).as_posix() + ("/" if p.is_dir() else "")
                  for p in pathlib.Path(base).rglob("*"))


@pytest.fixture
def src(tmp_path):
    root = tmp_path / "src"
    (root / "Photos" / "2024" / "summer").mkdir(parents=True)
    (root / "Photos" / "empty").mkdir()
    (root / "Photos" / "a.jpg").write_bytes(os.urandom(1000))
    (root / "Photos" / "2024" / "b.png").write_bytes(os.urandom(2000))
    (root / "Photos" / "2024" / "summer" / "clip.mp4").write_bytes(os.urandom(3000))
    (root / "notes.txt").write_text("hello")
    return root


def test_scan_classifies_files(src):
    events = run("scan", "--root", str(src))
    files = [f for e in events if e["type"] == "files" for f in e["files"]]
    assert {(f["r"], f["c"]) for f in files} == {
        (os.path.join("Photos", "a.jpg"), "Images"),
        (os.path.join("Photos", "2024", "b.png"), "Images"),
        (os.path.join("Photos", "2024", "summer", "clip.mp4"), "Vidéos"),
        ("notes.txt", "Documents"),
    }
    assert events[-1] == {"type": "done", "count": 4, "errors": 0, "cancelled": False}


def test_copy_file_by_type_then_rename_on_conflict(tmp_path, src):
    f = {"path": str(src / "Photos" / "a.jpg"), "rel": "Photos/a.jpg",
         "category": "Images", "size": 1000}
    dest = tmp_path / "dest"
    transfer(tmp_path, dest, files=[f])
    transfer(tmp_path, dest, files=[f])
    assert tree(dest) == ["Images/", "Images/a (1).jpg", "Images/a.jpg"]
    assert (dest / "Images" / "a.jpg").read_bytes() == (src / "Photos" / "a.jpg").read_bytes()


def test_skip_existing(tmp_path, src):
    f = {"path": str(src / "notes.txt"), "rel": "notes.txt", "category": "Documents", "size": 5}
    transfer(tmp_path, tmp_path / "dest", files=[f])
    events = transfer(tmp_path, tmp_path / "dest", conflict="skip", files=[f])
    result = next(e for e in events if e["type"] == "result")
    assert (result["status"], result["reason"]) == ("skipped", "exists")


def test_copy_whole_folder_keeps_structure(tmp_path, src):
    d = {"path": str(src / "Photos"), "rel": "Photos", "size": 6000}
    events = transfer(tmp_path, tmp_path / "dest", dirs=[d])
    result = next(e for e in events if e["type"] == "dir_result")
    assert (result["status"], result["files"]) == ("ok", 3)
    assert tree(tmp_path / "dest") == [
        "Photos/", "Photos/2024/", "Photos/2024/b.png", "Photos/2024/summer/",
        "Photos/2024/summer/clip.mp4", "Photos/a.jpg", "Photos/empty/"]


def test_move_folder_removes_source(tmp_path, src):
    d = {"path": str(src / "Photos"), "rel": "Photos", "size": 6000}
    transfer(tmp_path, tmp_path / "dest", mode="move", dirs=[d])
    assert not (src / "Photos").exists()
    assert (tmp_path / "dest" / "Photos" / "2024" / "summer" / "clip.mp4").exists()


def test_refuses_destination_inside_folder(tmp_path, src):
    d = {"path": str(src / "Photos"), "rel": "Photos", "size": 6000}
    events = transfer(tmp_path, src / "Photos" / "2024", dirs=[d])
    result = next(e for e in events if e["type"] == "dir_result")
    assert result["status"] == "failed"
    assert result["error"] == "the destination is inside this folder"


def test_missing_file_is_reported_not_fatal(tmp_path, src):
    missing = {"path": str(src / "nope.jpg"), "rel": "nope.jpg", "category": "Images", "size": 1}
    ok = {"path": str(src / "notes.txt"), "rel": "notes.txt", "category": "Documents", "size": 5}
    events = transfer(tmp_path, tmp_path / "dest", files=[missing, ok])
    results = [e for e in events if e["type"] == "result"]
    assert [r["status"] for r in results] == ["failed", "ok"]
    assert events[-1] == {"type": "done", "cancelled": False}


def test_messages_in_french(tmp_path, src):
    events = run("scan", "--root", str(tmp_path / "missing"), lang="fr")
    assert events[-1]["type"] == "error"
    assert "introuvable" in events[-1]["msg"]
