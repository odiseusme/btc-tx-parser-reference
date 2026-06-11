"""Deterministic differential fuzzer for the bounded parser/verifier.

The core library remains stdlib-only; this test uses only ``random`` (seeded
with a fixed constant) so runs are fully reproducible and finish well under
ten seconds.

Generated subset
================
Each generated transaction stays strictly within the bounded subset that
``_verify_parser_bytes`` (and ``parse_bitcoin_tx``) accept, derived directly
from btc_ergo_proof.py:

  * Legacy (non-witness) serialization only. The byte after the 4-byte version
    is the input count (1 or 2), never 0x00, so the SegWit marker is never
    misdetected and ``stripped == raw``.
  * Input count is 1 or 2 (single-byte CompactSize); each input is the fixed
    layout [prev_txid:32][prev_vout:4][script_len:1][script_sig][sequence:4]
    with ``script_len < 0xFD``.
  * Output count is 1..4 (single-byte CompactSize); each output is
    [value:8 LE][script_len:1][script_pubkey] with ``1 <= script_len < 0xFD``
    (script_len >= 1 so every output can be a script-hash match target).
  * 4-byte locktime immediately ends the transaction (no trailing bytes), so
    the verifier's locktime/length check passes structurally.
  * Output values occasionally take the boundary values 0, exactly
    MAX_BTC_SATOSHIS, and MAX_BTC_SATOSHIS + 1 (over-supply). Mirroring the
    contract semantics from PR #6, an over-supply value is only ever assigned
    to a NON-target output: the proof target is always chosen from outputs with
    value <= MAX_BTC_SATOSHIS, so over-supply is a per-output non-match rather
    than something that could be "proven".

Per generated transaction the following invariants are checked:
  a. Roundtrip: build_bounded_output_proof on a random valid output index
     verifies True with verify_bounded_parser.
  b. Amount semantics: with R6 <= the target's value the amount verifier is
     True; with R6 = value + 1 the verifier's result equals whether ANY OTHER
     output independently satisfies both the script-hash match and the minimum
     (computed by walking the generator's own ground-truth output list).
  c. Model agreement: parse_bitcoin_tx reports the same output count, values,
     and script bytes as the generator's ground truth.
  d. Mutation: flipping one bit of the tx bytes without updating R4 makes
     verification False.
"""

from __future__ import annotations

import hashlib
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from btc_ergo_proof import (
    MAX_BTC_SATOSHIS,
    build_bounded_output_proof,
    verify_bounded_parser,
    verify_bounded_parser_amount,
)
from btc_tx_parser import parse_bitcoin_tx

SEED = 0xB7C_E2_60  # fixed: keep runs reproducible
ITERATIONS = 200


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gen_value(rng: random.Random, *, allow_oversupply: bool) -> int:
    """Pick an output value, occasionally hitting boundary cases."""
    roll = rng.random()
    if roll < 0.08:
        return 0
    if roll < 0.16:
        return MAX_BTC_SATOSHIS
    if allow_oversupply and roll < 0.24:
        return MAX_BTC_SATOSHIS + 1
    return rng.randint(0, MAX_BTC_SATOSHIS)


def _gen_transaction(rng: random.Random) -> dict:
    """Build one transaction in the bounded subset.

    Returns the raw hex plus the generator's ground truth: the ordered list of
    (value, script_bytes) outputs and the chosen proof target index.
    """
    input_count = rng.choice([1, 2])
    output_count = rng.randint(1, 4)

    data = bytearray(rng.randbytes(4))  # version (any 4 bytes; never affects subset)
    data.append(input_count)
    for _ in range(input_count):
        data += rng.randbytes(32)        # prev_txid
        data += rng.randbytes(4)         # prev_vout
        sig_len = rng.randint(0, 40)     # < 0xFD
        data.append(sig_len)
        data += rng.randbytes(sig_len)   # script_sig
        data += rng.randbytes(4)         # sequence

    data.append(output_count)
    outputs = []  # ground truth: list of {"value", "script"}
    for _ in range(output_count):
        # Over-supply is allowed here but the target is later chosen only from
        # outputs whose value <= MAX, so an over-supply output is never a target.
        value = _gen_value(rng, allow_oversupply=True)
        script_len = rng.randint(1, 40)  # >= 1 so the output can match a hash
        script = rng.randbytes(script_len)
        outputs.append({"value": value, "script": script})

    # Choose the proof target from non-oversupply outputs only.
    eligible = [i for i, o in enumerate(outputs) if o["value"] <= MAX_BTC_SATOSHIS]
    if not eligible:
        outputs[0]["value"] = rng.randint(0, MAX_BTC_SATOSHIS)
        eligible = [0]
    target_idx = rng.choice(eligible)

    # Occasionally graft the target's script onto another output with a value
    # above the target's, so invariant (b)'s "any other output" branch can be
    # genuinely True (a matching, sufficiently-funded sibling).
    target_value = outputs[target_idx]["value"]
    if output_count > 1 and target_value < MAX_BTC_SATOSHIS and rng.random() < 0.30:
        others = [i for i in range(output_count) if i != target_idx]
        sib = rng.choice(others)
        outputs[sib]["script"] = outputs[target_idx]["script"]
        outputs[sib]["value"] = rng.randint(target_value + 1, MAX_BTC_SATOSHIS)

    for o in outputs:
        data += o["value"].to_bytes(8, "little")
        data.append(len(o["script"]))
        data += o["script"]

    data += rng.randbytes(4)  # locktime; transaction ends here (no trailing)

    return {
        "raw_hex": bytes(data).hex(),
        "outputs": outputs,
        "target_idx": target_idx,
    }


class DifferentialFuzzTest(unittest.TestCase):
    def test_bounded_subset_invariants(self):
        rng = random.Random(SEED)
        for i in range(ITERATIONS):
            with self.subTest(iteration=i):
                tx = _gen_transaction(rng)
                self._check_one(rng, tx)

    def _check_one(self, rng: random.Random, tx: dict) -> None:
        raw_hex = tx["raw_hex"]
        outputs = tx["outputs"]
        target_idx = tx["target_idx"]
        target = outputs[target_idx]
        target_value = target["value"]
        r5_hex = _sha256_hex(target["script"])

        self.assertLessEqual(
            target_value, MAX_BTC_SATOSHIS, "target must never be over-supply"
        )

        # (a) Roundtrip.
        proof = build_bounded_output_proof(raw_hex, output_index=target_idx)
        self.assertTrue(
            verify_bounded_parser(proof),
            msg=f"roundtrip failed for target {target_idx}",
        )

        # (b) Amount semantics.
        at_or_below = dict(proof)
        at_or_below["contract"] = "btc_verify_parser_amount"
        at_or_below["registers"] = dict(proof["registers"], R6=target_value)
        self.assertTrue(
            verify_bounded_parser_amount(at_or_below),
            msg="R6 <= target value should verify True",
        )

        r6_above = target_value + 1
        above = dict(proof)
        above["contract"] = "btc_verify_parser_amount"
        above["registers"] = dict(proof["registers"], R6=r6_above)
        # Independent ground-truth walk: any OTHER output that both matches the
        # target script hash and meets the minimum (and is within supply).
        expected_above = any(
            i != target_idx
            and _sha256_hex(o["script"]) == r5_hex
            and r6_above <= o["value"] <= MAX_BTC_SATOSHIS
            for i, o in enumerate(outputs)
        )
        self.assertEqual(
            verify_bounded_parser_amount(above),
            expected_above,
            msg="R6 = value+1 result must match independent ground truth",
        )

        # (c) Model agreement.
        parsed = parse_bitcoin_tx(raw_hex)
        self.assertFalse(parsed["is_segwit"])
        self.assertEqual(parsed["output_count"], len(outputs))
        self.assertEqual(len(parsed["outputs"]), len(outputs))
        for parsed_out, truth in zip(parsed["outputs"], outputs):
            self.assertEqual(parsed_out["value_satoshis"], truth["value"])
            self.assertEqual(parsed_out["script_pubkey_hex"], truth["script"].hex())

        # (d) Mutation: flip one bit, keep R4, expect rejection.
        raw = bytearray(bytes.fromhex(raw_hex))
        pos = rng.randrange(len(raw))
        raw[pos] ^= 1 << rng.randrange(8)
        mutated = dict(proof)
        mutated["context"] = dict(proof["context"], **{"1": bytes(raw).hex()})
        self.assertFalse(
            verify_bounded_parser(mutated),
            msg=f"mutation at byte {pos} should fail verification",
        )


if __name__ == "__main__":
    unittest.main()
