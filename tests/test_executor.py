from pathlib import Path

from capoeira_agent.executor import Executor
from capoeira_agent.steps import Step, _encode_b64


def _step(tool, **params):
    return Step(tool=tool, params=params)


def test_read_file(tmp_path):
    (tmp_path / "a.txt").write_text("conteudo", encoding="utf-8")
    ex = Executor(tmp_path)
    res = ex.apply(_step("read_file", path="a.txt"))
    assert res.ok and res.output == "conteudo"


def test_list_dir(tmp_path):
    (tmp_path / "dir1").mkdir()
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    ex = Executor(tmp_path)
    res = ex.apply(_step("list_dir", path="."))
    assert res.ok
    assert "dir1/" in res.output and "f.txt" in res.output


def test_write_file_create(tmp_path):
    ex = Executor(tmp_path)
    res = ex.apply(_step("write_file", file_path="novo.txt", action="create_file",
                         code_content=_encode_b64("ola\n")))
    assert res.ok
    assert (tmp_path / "novo.txt").read_text() == "ola\n"


def test_write_file_bad_base64_not_written(tmp_path):
    ex = Executor(tmp_path)
    res = ex.apply(_step("write_file", file_path="x.txt", action="create_file", code_content="!!inválido"))
    assert not res.ok
    assert not (tmp_path / "x.txt").exists()


def test_run_python_simple(tmp_path):
    ex = Executor(tmp_path, python="python")
    res = ex.apply(_step("run_python", code=_encode_b64("print(21*2)")))
    assert res.ok
    assert "42" in res.output


def test_unknown_tool():
    from capoeira_agent.core.registry import CommandRegistry

    ex = Executor(Path("."), registry=CommandRegistry())
    res = ex.apply(_step("nao_existe", x=1))
    assert not res.ok and "desconhecida" in res.error