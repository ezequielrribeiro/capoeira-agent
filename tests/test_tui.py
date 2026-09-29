from prompt_toolkit import PromptSession
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.styles import Style

from capoeira_agent.tui.app import approval_style


def test_approval_style_is_valid_style_object():
    s = approval_style()
    assert isinstance(s, Style)
    assert s.invalidation_hash() is not None


def test_approval_prompt_accepts_style_object():
    with create_pipe_input() as inp:
        inp.send_text("y\n")
        ps = PromptSession(input=inp, output=DummyOutput())
        out = ps.prompt("permitir? ", style=approval_style())
    assert out == "y"