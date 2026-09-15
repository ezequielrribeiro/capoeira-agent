import pytest

from capoeira_agent.applier import ChangeApplier


def test_create_file(tmp_path):
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "app/x.py", "action": "create_file", "code_content": "print(1)\n"}])
    assert res.ok
    assert (tmp_path / "app" / "x.py").read_text() == "print(1)\n"


def test_create_file_exists_fails_and_nothing_written(tmp_path):
    (tmp_path / "a.txt").write_text("existe", encoding="utf-8")
    app = ChangeApplier(tmp_path)
    res = app.apply(
        [
            {"file_path": "a.txt", "action": "create_file", "code_content": "novo"},
            {"file_path": "novo.txt", "action": "create_file", "code_content": "n"},
        ]
    )
    assert not res.ok
    assert not (tmp_path / "novo.txt").exists()  # all-or-nothing


def test_replace_symbol(tmp_path):
    (tmp_path / "a.txt").write_text("foo bar foo", encoding="utf-8")
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "a.txt", "action": "replace", "target_symbol": "bar", "code_content": "BAZ"}])
    assert res.ok
    assert (tmp_path / "a.txt").read_text() == "foo BAZ foo"


def test_replace_symbol_missing_fails(tmp_path):
    (tmp_path / "a.txt").write_text("foo", encoding="utf-8")
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "a.txt", "action": "replace_symbol", "target_symbol": "zzz", "code_content": "x"}])
    assert not res.ok


def test_patch_diff(tmp_path):
    (tmp_path / "a.txt").write_text("linha1\nlinha2\nlinha3\n", encoding="utf-8")
    diff = (
        "--- a/a.txt\n+++ b/a.txt\n"
        "@@ -1,3 +1,3 @@\n linha1\n-linha2\n+LINHA2\n linha3\n"
    )
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "a.txt", "action": "patch_diff", "code_content": diff}])
    assert res.ok
    assert (tmp_path / "a.txt").read_text() == "linha1\nLINHA2\nlinha3\n"


def test_patch_diff_context_mismatch_fails(tmp_path):
    (tmp_path / "a.txt").write_text("aaa\nbbb\n", encoding="utf-8")
    diff = "@@ -1,2 +1,2 @@\n inesperado\n-bbb\n+ccc\n"
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "a.txt", "action": "patch_diff", "code_content": diff}])
    assert not res.ok
    assert (tmp_path / "a.txt").read_text() == "aaa\nbbb\n"  # nada foi gravado


def test_path_traversal_blocked(tmp_path):
    app = ChangeApplier(tmp_path)
    res = app.apply([{"file_path": "../escaped.txt", "action": "create_file", "code_content": "x"}])
    assert not res.ok
    assert not (tmp_path.parent / "escaped.txt").exists()