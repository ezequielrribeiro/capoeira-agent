import pytest

from capoeira_agent.steps import _decode_b64, _encode_b64, _split_pipe_fields, parse_tool_calls


def test_split_pipe_fields():
    assert _split_pipe_fields("item=leite | quantidade=2") == ["item=leite", "quantidade=2"]
    assert _split_pipe_fields("cmd='php -l app | tail -5' | x=1") == ["cmd='php -l app | tail -5'", "x=1"]


def test_parse_tool_calls_simple():
    lines = "[TOOL_CALL] run_shell | cmd='ls -la' | timeout=5"
    steps = parse_tool_calls(lines)
    assert len(steps) == 1
    assert steps[0].tool == "run_shell"
    assert steps[0].params["cmd"] == "ls -la"
    assert steps[0].params["timeout"] == 5


def test_parse_tool_calls_multiple_and_types():
    content = "prosa\n[TOOL_CALL] write_file | file_path='a.txt' | action=create_file | code_content=PD9waHAK\n\n"
    steps = parse_tool_calls(content)
    assert len(steps) == 1
    assert steps[0].params["action"] == "create_file"
    assert steps[0].params["code_content"] == "PD9waHAK"


def test_parse_tool_calls_prose_only():
    assert parse_tool_calls("apenas prosa") == []
    assert parse_tool_calls("") == []


def test_parse_tool_calls_truncated_is_skipped():
    # aspas simples não fechadas => linha cortada => não executar
    content = "[TOOL_CALL] write_file | code_content='PD9waHAK"
    assert parse_tool_calls(content) == []


def test_base64_roundtrip():
    assert _decode_b64(_encode_b64("<?php echo 1;")) == "<?php echo 1;"


def test_base64_invalid():
    with pytest.raises(ValueError):
        _decode_b64("!!!notbase64!!!")
    with pytest.raises(ValueError):
        _decode_b64("PD9")  # tamanho %4 != 0
    with pytest.raises(ValueError):
        _decode_b64("//8=")  # bytes não-UTF-8