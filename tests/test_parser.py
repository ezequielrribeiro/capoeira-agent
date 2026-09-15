from capoeira_agent.core.parser import parse_flags, parse_line


def test_parse_line_command():
    name, args = parse_line("/init")
    assert name == "/init" and args == []


def test_parse_line_with_args():
    name, args = parse_line("/generate-plugin --name meu-comando")
    assert name == "/generate-plugin"
    assert args == ["--name", "meu-comando"]


def test_parse_line_plain_text():
    name, args = parse_line("escreva um teste")
    assert name == "" and args == ["escreva", "um", "teste"]


def test_parse_flags():
    flags = parse_flags(["--name", "x", "--force"])
    assert flags == {"name": "x", "force": True}


def test_parse_line_empty():
    assert parse_line("") == ("", [])
    assert parse_line("   ") == ("", [])