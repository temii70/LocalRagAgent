"""Offline regressions for checksum portability; no inference dependencies."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class PortabilityTests(unittest.TestCase):
    def test_json_writer_uses_utf8_lf_bytes(self):
        spec = importlib.util.spec_from_file_location("prepare_public", ROOT / "prepare_public.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "queries.json"
            module.dump_json(target, {"claim": "caf\u00e9"})
            self.assertEqual(target.read_bytes(), '{\n  "claim": "caf\u00e9"\n}\n'.encode("utf-8"))

    def test_published_results_verify_in_checkout(self):
        result = subprocess.run([sys.executable, str(ROOT / "verify_public.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
