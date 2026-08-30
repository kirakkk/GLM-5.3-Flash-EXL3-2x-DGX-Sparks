#!/usr/bin/env python3
"""Regression test for caller overrides that must win over ``.env``."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _bash_command(script: Path) -> list[str]:
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if git_bash.is_file():
            posix_script = f"/{script.drive[0].lower()}{script.as_posix()[2:]}"
            return [str(git_bash), posix_script]
    bash = shutil.which("bash")
    assert bash, "bash is required for launcher regression tests"
    return [bash, str(script)]


def test_default_multimodal_limit_allows_eight_images() -> None:
    expected = 'LIMIT_MM=\'{"image":8,"video":1}\''
    assert expected in (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "    " + expected in (ROOT / "start.sh").read_text(encoding="utf-8")


def test_max_num_seqs_inline_override_wins() -> None:
    source = (ROOT / "start.sh").read_text(encoding="utf-8")
    marker = "# ----------------------------- configuration -------------------------------"
    preamble, separator, _rest = source.partition(marker)
    assert separator, "start.sh configuration marker is missing"

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        script = tmp / "start.sh"
        script.write_text(
            preamble
            + '\nprintf "MAX_NUM_SEQS=%s\\n" "${MAX_NUM_SEQS:-unset}"\n'
        )
        script.chmod(0o755)
        (tmp / ".env").write_text("MAX_NUM_SEQS=2\n")

        env = os.environ.copy()
        env["MAX_NUM_SEQS"] = "4"
        result = subprocess.run(
            _bash_command(script),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

    assert result.stdout.strip() == "MAX_NUM_SEQS=4"


if __name__ == "__main__":
    test_default_multimodal_limit_allows_eight_images()
    test_max_num_seqs_inline_override_wins()
    print("start.sh caller override regression OK")
