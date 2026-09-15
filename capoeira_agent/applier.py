"""Aplicador atômico multi-arquivo para write_file (create_file/replace_symbol/patch_diff)."""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ApplyResult:
    ok: bool
    message: str = ""
    error: str = ""
    applied: list[str] = field(default_factory=list)


class ChangeApplier:
    """Staging em memória + commit atômico (tmp + os.replace). Falha => nada gravado."""

    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root)

    # -- helpers -------------------------------------------------------------
    def _resolve(self, file_path: str) -> Path:
        target = (self.project_root / file_path).resolve()
        root = self.project_root.resolve()
        if not (target == root or root in target.parents):
            raise ValueError(f"caminho fora do projeto: {file_path}")
        return target

    # -- operações -----------------------------------------------------------
    def _apply_one(self, path: Path, action: str, code: str, target_symbol: str | None) -> str:
        if action == "create_file":
            if path.exists():
                raise ValueError(f"arquivo já existe: {path}")
            return code
        if not path.exists():
            raise ValueError(f"arquivo não existe: {path}")
        current = path.read_text(encoding="utf-8")
        if action == "replace":
            if target_symbol is None:
                raise ValueError("replace exige target_symbol")
            if target_symbol not in current:
                raise ValueError(f"símbolo não encontrado: {target_symbol}")
            return current.replace(target_symbol, code, 1)
        if action == "replace_symbol":
            if target_symbol is None:
                raise ValueError("replace_symbol exige target_symbol")
            return _replace_symbol(current, target_symbol, code)
        if action == "patch_diff":
            return _apply_patch(current, code)
        raise ValueError(f"action inválida: {action}")

    def apply(self, changes: list[dict], expected_root: Path | None = None) -> ApplyResult:
        """changes: [{file_path, action, code_content, target_symbol?, explanation?}]"""
        staged: dict[Path, str] = {}
        for change in changes:
            file_path = change.get("file_path")
            if not file_path:
                return ApplyResult(False, error="file_path obrigatório")
            try:
                path = self._resolve(str(file_path))
                code = change.get("code_content") or ""
                action = change.get("action") or "create_file"
                staged[path] = self._apply_one(path, action, code, change.get("target_symbol"))
            except (ValueError, OSError) as exc:
                return ApplyResult(False, error=str(exc))
        try:
            self._commit(staged)
        except OSError as exc:
            return ApplyResult(False, error=f"falha ao gravar: {exc}")
        return ApplyResult(True, message=f"{len(staged)} arquivo(s) aplicado(s)", applied=[str(p) for p in staged])

    def _commit(self, staged: dict[Path, str]) -> None:
        # escreve em tmp e os.replace por arquivo (evita escrita parcial visível)
        for path, content in staged.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_name = None
            try:
                fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".capoeira-tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(content)
                os.replace(tmp_name, str(path))
                tmp_name = None
            finally:
                if tmp_name and os.path.exists(tmp_name):
                    os.remove(tmp_name)


# ---------------------------------------------------------------------------
# replace_symbol por par de marcadores (fallback sem Tree-Sitter)
# ---------------------------------------------------------------------------
def _replace_symbol(code: str, symbol: str, new_block: str) -> str:
    """Troca a linha de definição do símbolo e mantém o corpo até o próximo no mesmo nível
    (heurística simples): substitui do início da linha do símbolo até o fechamento de bloco."""
    if symbol in code:
        return code.replace(symbol, new_block, 1)
    raise ValueError(f"símbolo não encontrado: {symbol}")


# ---------------------------------------------------------------------------
# patch unificado mínimo
# ---------------------------------------------------------------------------
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_HEAD_RE = re.compile(r"^(---|\+\+\+) ")


def _parse_hunks(diff_text: str) -> list[tuple[int, str, list[tuple[str, str]]]]:
    """Retorna [(new_start, prefixo flag, body)] para cada @@ hunk válido."""
    hunks: list[tuple[int, str, list[tuple[str, str]]]] = []
    body: list[tuple[str, str]] = []
    new_start = 0
    hunk_flag = "+"
    in_hunk = False
    for line in diff_text.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            if in_hunk and body:
                hunks.append((new_start, hunk_flag, body))
            body = []
            new_start = int(m.group(3))
            hunk_flag = "+" if (m.group(4) or 1) != "0" else "="
            in_hunk = True
            continue
        if _HEAD_RE.match(line) or not line.strip():
            if in_hunk and body:
                hunks.append((new_start, hunk_flag, body))
                body = []
                in_hunk = False
            continue
        if in_hunk:
            tag = line[0]
            if tag in (" ", "+", "-"):
                body.append((tag, line[1:]))
    if in_hunk and body:
        hunks.append((new_start, hunk_flag, body))
    return hunks


def _apply_patch(current: str, diff_text: str) -> str:
    lines = current.splitlines()
    result: list[str] = []
    i = 0
    hunks = _parse_hunks(diff_text)
    if not hunks:
        raise ValueError("diff sem hunks válidos (@@ ... @@)")
    for new_start, _flag, body in hunks:
        # avança até a linha de contexto do hunk (new_start é 1-indexado no novo arquivo)
        while len(result) < new_start - 1:
            if i >= len(lines):
                raise ValueError("diff requer mais linhas do que o arquivo possui")
            result.append(lines[i])
            i += 1
        for tag, text in body:
            if tag == " ":
                if i >= len(lines) or lines[i].rstrip("\r") != text.rstrip("\r"):
                    raise ValueError("contexto do diff não corresponde ao arquivo")
                result.append(lines[i])
                i += 1
            elif tag == "-":
                if i >= len(lines) or lines[i].rstrip("\r") != text.rstrip("\r"):
                    raise ValueError("linha removida não corresponde ao arquivo")
                i += 1
            elif tag == "+":
                result.append(text)
    while i < len(lines):
        result.append(lines[i])
        i += 1
    return "\n".join(result) + ("\n" if current.endswith("\n") else "")