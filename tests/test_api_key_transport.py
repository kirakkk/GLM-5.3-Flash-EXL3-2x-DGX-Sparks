#!/usr/bin/env python3
"""Static safety contract for bearer-token transport in start.sh."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ApiKeyTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "start.sh").read_text(encoding="utf-8")

    def test_native_vllm_api_key_is_forwarded_to_both_nodes(self) -> None:
        self.assertIn('VLLM_API_KEY="${VLLM_API_KEY:-}"', self.source)
        self.assertIn('serve_env+=" -e VLLM_API_KEY=', self.source)
        self.assertIn('-e VLLM_API_KEY="$VLLM_API_KEY"', self.source)

    def test_launcher_never_builds_api_key_cli_argument(self) -> None:
        self.assertIsNone(
            re.search(r"ARGS\s*\+?=.*--api-key", self.source),
            "API keys in ARGS are printed by the generated launcher and vLLM",
        )


if __name__ == "__main__":
    unittest.main()
