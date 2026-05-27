import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from btc_tx_parser import display_to_natural, parse_bitcoin_tx
from btc_ergo_proof import (
    build_bounded_output_proof,
    double_sha256,
    verify_bounded_parser,
)

from fixtures import ROSEN_BRIDGE_TX_HEX, ROSEN_TXID_DISPLAY, SATOSHI_TX_HEX


class BitcoinProofReferenceTests(unittest.TestCase):
    def test_builds_bounded_output_proof_for_rosen_fixture(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)

        self.assertEqual(proof["contract"], "btc_verify_parser")
        self.assertEqual(proof["bitcoin"]["txid_display"], ROSEN_TXID_DISPLAY)
        self.assertEqual(proof["selected_output"]["index"], 1)
        self.assertEqual(proof["selected_output"]["value_satoshis"], 300000)
        self.assertEqual(proof["registers"]["R4"], display_to_natural(ROSEN_TXID_DISPLAY))
        self.assertEqual(
            proof["registers"]["R5"],
            hashlib.sha256(bytes.fromhex(proof["selected_output"]["script_pubkey_hex"])).hexdigest(),
        )
        self.assertTrue(verify_bounded_parser(proof))

    def test_rejects_display_order_txid_in_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        proof["registers"]["R4"] = proof["bitcoin"]["txid_display"]

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_full_segwit_raw_bytes_in_context_var(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        proof["context"]["1"] = ROSEN_BRIDGE_TX_HEX

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_script_hash_that_only_matches_input_script_sig(self):
        tx = parse_bitcoin_tx(SATOSHI_TX_HEX)
        proof = build_bounded_output_proof(SATOSHI_TX_HEX, output_index=0)
        proof["registers"]["R5"] = hashlib.sha256(
            bytes.fromhex(tx["inputs"][0]["script_sig"])
        ).hexdigest()

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_truncated_transaction_even_with_matching_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        tx_bytes = bytes.fromhex(proof["context"]["1"])[:-8]
        self._replace_context_bytes_and_r4(proof, tx_bytes)

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_trailing_bytes_even_with_matching_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        tx_bytes = bytes.fromhex(proof["context"]["1"]) + b"\x00"
        self._replace_context_bytes_and_r4(proof, tx_bytes)

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_more_than_four_outputs_even_with_matching_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        tx_bytes = bytearray.fromhex(proof["context"]["1"])
        inputs_end = 46
        tx_bytes[inputs_end] = 5
        self._replace_context_bytes_and_r4(proof, bytes(tx_bytes))

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_empty_script_hash_even_with_matching_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        tx_bytes = bytearray.fromhex(proof["context"]["1"])
        output1_script_len_offset = 117
        tx_bytes[output1_script_len_offset] = 0
        proof["registers"]["R5"] = hashlib.sha256(b"").hexdigest()
        self._replace_context_bytes_and_r4(proof, bytes(tx_bytes))

        self.assertFalse(verify_bounded_parser(proof))

    def test_rejects_unsupported_compactsize_even_with_matching_r4(self):
        proof = build_bounded_output_proof(ROSEN_BRIDGE_TX_HEX, output_index=1)
        tx_bytes = bytearray.fromhex(proof["context"]["1"])
        output1_script_len_offset = 117
        tx_bytes[output1_script_len_offset] = 0xFD
        self._replace_context_bytes_and_r4(proof, bytes(tx_bytes))

        self.assertFalse(verify_bounded_parser(proof))

    def test_cli_builds_json_proof_that_verifies_locally(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "btc_ergo_proof.py"),
                "build",
                "--raw-tx",
                ROSEN_BRIDGE_TX_HEX,
                "--output-index",
                "1",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        proof = json.loads(completed.stdout)

        self.assertEqual(proof["selected_output"]["index"], 1)
        self.assertTrue(verify_bounded_parser(proof))

    def test_valid_json_vectors_verify_locally(self):
        paths = sorted((ROOT / "test-vectors" / "valid").glob("*.proof.json"))
        self.assertGreaterEqual(len(paths), 1)
        for path in paths:
            with self.subTest(vector=path.name):
                vector = self._load_vector(path)
                self.assertTrue(verify_bounded_parser(vector))

    def test_invalid_json_vectors_fail_locally(self):
        paths = sorted((ROOT / "test-vectors" / "invalid").glob("*.proof.json"))
        self.assertGreaterEqual(len(paths), 1)
        for path in paths:
            with self.subTest(vector=path.name):
                vector = self._load_vector(path)
                self.assertFalse(verify_bounded_parser(vector))

    def _replace_context_bytes_and_r4(self, proof, tx_bytes):
        proof["context"]["1"] = tx_bytes.hex()
        proof["registers"]["R4"] = double_sha256(tx_bytes).hex()

    def _load_vector(self, path):
        return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
