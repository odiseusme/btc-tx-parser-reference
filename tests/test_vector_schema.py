"""Validate every public proof vector against the JSON Schema.

The core reference library (btc_tx_parser.py / btc_ergo_proof.py) remains
stdlib-only. ``jsonschema`` is a dev/test dependency only (see
requirements-dev.txt) and is never imported by the library itself; this test
is skipped if it is not installed.

The schema (schema/btc-ergo-proof-v1.schema.json) is strict on the
consensus-relevant fields and permissive on the informational metadata. Every
test-vectors/**/*.proof.json file must validate against it.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "btc-ergo-proof-v1.schema.json"
VECTOR_PATHS = sorted((ROOT / "test-vectors").rglob("*.proof.json"))

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only without the dev dep
    jsonschema = None


@unittest.skipIf(jsonschema is None, "jsonschema dev dependency not installed")
class VectorSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def test_vectors_exist(self) -> None:
        self.assertTrue(VECTOR_PATHS, "no *.proof.json vectors discovered")

    def test_every_vector_validates(self) -> None:
        for path in VECTOR_PATHS:
            with self.subTest(vector=path.relative_to(ROOT).as_posix()):
                proof = json.loads(path.read_text(encoding="utf-8"))
                errors = sorted(
                    self.validator.iter_errors(proof),
                    key=lambda e: list(e.absolute_path),
                )
                self.assertEqual(
                    errors,
                    [],
                    msg="; ".join(
                        f"{list(e.absolute_path)}: {e.message}" for e in errors
                    ),
                )


if __name__ == "__main__":
    unittest.main()
