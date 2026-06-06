"""
Build and locally verify Ergo context data for bounded Bitcoin tx proofs.

This module models the current canonical contract, btc_verify_parser.ergo:
R4 is the natural-order Bitcoin txid, R5 is SHA-256(scriptPubKey), and
context var 1 is the non-witness transaction serialization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Any

from btc_tx_parser import parse_bitcoin_tx


MAX_BTC_SATOSHIS = 21_000_000 * 100_000_000


def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def build_bounded_output_proof(
    raw_tx_hex: str,
    *,
    output_index: int | None = None,
    script_hash: str | None = None,
    min_satoshis: int | None = None,
) -> dict[str, Any]:
    """Build the register/context payload for the bounded parser contract."""
    tx = parse_bitcoin_tx(raw_tx_hex)
    outputs = tx["outputs"]

    if output_index is None and script_hash is None:
        raise ValueError("Provide output_index or script_hash")

    if output_index is not None:
        if output_index < 0 or output_index >= len(outputs):
            raise ValueError(f"output_index {output_index} out of range")
        selected_index = output_index
    else:
        wanted = _normalize_hex(script_hash or "", expected_bytes=32)
        matches = [
            i for i, out in enumerate(outputs)
            if out["script_hash_sha256"] == wanted
        ]
        if not matches:
            raise ValueError("script_hash does not match any parsed output")
        if len(matches) > 1:
            raise ValueError(
                f"script_hash matches multiple outputs (indices {matches}). "
                "Pass output_index explicitly to disambiguate."
            )
        selected_index = matches[0]

    selected = outputs[selected_index]
    proof = {
        "version": "btc-ergo-proof-v1",
        "contract": "btc_verify_parser_amount" if min_satoshis is not None else "btc_verify_parser",
        "bitcoin": {
            "txid_display": tx["txid"],
            "txid_natural": tx["txid_natural"],
            "is_segwit": tx["is_segwit"],
            "input_count": tx["input_count"],
            "output_count": tx["output_count"],
            "stripped_size_bytes": len(tx["stripped_tx_hex"]) // 2,
        },
        "registers": {
            "R4": tx["txid_natural"],
            "R5": selected["script_hash_sha256"],
        },
        "context": {
            "1": tx["stripped_tx_hex"],
        },
        "selected_output": {
            "index": selected_index,
            "value_satoshis": selected["value_satoshis"],
            "script_pubkey_hex": selected["script_pubkey_hex"],
            "script_hash_sha256": selected["script_hash_sha256"],
        },
    }
    if min_satoshis is not None:
        _validate_satoshis(min_satoshis, "min_satoshis")
        proof["registers"]["R6"] = min_satoshis
    return proof


def verify_bounded_parser(proof: dict[str, Any]) -> bool:
    """Return True if the proof satisfies btc_verify_parser.ergo semantics."""
    try:
        tx_bytes = bytes.fromhex(proof["context"]["1"])
        expected_txid = _normalize_hex(proof["registers"]["R4"], expected_bytes=32)
        expected_script_hash = _normalize_hex(proof["registers"]["R5"], expected_bytes=32)
        return _verify_parser_bytes(tx_bytes, expected_txid, expected_script_hash)
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def verify_bounded_parser_amount(
    proof: dict[str, Any],
    min_satoshis: int | None = None,
) -> bool:
    """Return True if the proof satisfies the amount-binding parser semantics."""
    try:
        tx_bytes = bytes.fromhex(proof["context"]["1"])
        expected_txid = _normalize_hex(proof["registers"]["R4"], expected_bytes=32)
        expected_script_hash = _normalize_hex(proof["registers"]["R5"], expected_bytes=32)
        required = proof["registers"].get("R6") if min_satoshis is None else min_satoshis
        required = _validate_satoshis(required, "min_satoshis")
        return _verify_parser_bytes(
            tx_bytes,
            expected_txid,
            expected_script_hash,
            min_satoshis=required,
        )
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return False


def _verify_parser_bytes(
    tx_bytes: bytes,
    expected_txid: str,
    expected_script_hash: str,
    *,
    min_satoshis: int | None = None,
) -> bool:
    # Mirrors the on-chain bounded parser assumptions exactly
    # (1-2 inputs, 1-4 outputs, single-byte CompactSize, non-witness bytes).
    # NOT a general Bitcoin transaction parser. See LIMITATIONS.md and SPEC.md.
    size_ok = len(tx_bytes) >= 61
    txid_ok = double_sha256(tx_bytes).hex() == expected_txid

    input_count = _read_byte(tx_bytes, 4)
    input_count_ok = input_count in (1, 2)

    input1_script_len_ok = _read_byte(tx_bytes, 5 + 36) < 0xFD
    after_input1 = _input_end(tx_bytes, 5)

    if input_count == 2:
        input2_script_len_ok = _read_byte(tx_bytes, after_input1 + 36) < 0xFD
        after_input2 = _input_end(tx_bytes, after_input1)
    else:
        input2_script_len_ok = True
        after_input2 = after_input1

    inputs_end = after_input2
    output_count = _read_byte(tx_bytes, inputs_end)
    output_count_ok = 1 <= output_count <= 4

    output1_start = inputs_end + 1
    output1_script_len_ok = _read_byte(tx_bytes, output1_start + 8) < 0xFD
    match1 = _output_matches(
        tx_bytes,
        output1_start,
        expected_script_hash,
        min_satoshis=min_satoshis,
    )
    after_output1 = _output_end(tx_bytes, output1_start)

    if output_count >= 2:
        output2_script_len_ok = _read_byte(tx_bytes, after_output1 + 8) < 0xFD
        match2 = _output_matches(
            tx_bytes,
            after_output1,
            expected_script_hash,
            min_satoshis=min_satoshis,
        )
        after_output2 = _output_end(tx_bytes, after_output1)
    else:
        output2_script_len_ok = True
        match2 = False
        after_output2 = after_output1

    if output_count >= 3:
        output3_script_len_ok = _read_byte(tx_bytes, after_output2 + 8) < 0xFD
        match3 = _output_matches(
            tx_bytes,
            after_output2,
            expected_script_hash,
            min_satoshis=min_satoshis,
        )
        after_output3 = _output_end(tx_bytes, after_output2)
    else:
        output3_script_len_ok = True
        match3 = False
        after_output3 = after_output2

    if output_count == 4:
        output4_script_len_ok = _read_byte(tx_bytes, after_output3 + 8) < 0xFD
        match4 = _output_matches(
            tx_bytes,
            after_output3,
            expected_script_hash,
            min_satoshis=min_satoshis,
        )
        after_output4 = _output_end(tx_bytes, after_output3)
    else:
        output4_script_len_ok = True
        match4 = False
        after_output4 = after_output3

    outputs_end = after_output4
    locktime_ok = outputs_end == len(tx_bytes) - 4
    any_output_matches = match1 or match2 or match3 or match4
    all_varints_ok = all(
        [
            input1_script_len_ok,
            input2_script_len_ok,
            output1_script_len_ok,
            output2_script_len_ok,
            output3_script_len_ok,
            output4_script_len_ok,
        ]
    )

    return all(
        [
            size_ok,
            txid_ok,
            input_count_ok,
            output_count_ok,
            all_varints_ok,
            locktime_ok,
            any_output_matches,
        ]
    )


def _read_byte(data: bytes, pos: int) -> int:
    return data[pos]


def _input_end(data: bytes, start: int) -> int:
    script_len = _read_byte(data, start + 36)
    return start + 37 + script_len + 4


def _output_end(data: bytes, start: int) -> int:
    script_len = _read_byte(data, start + 8)
    return start + 9 + script_len


def _output_matches(
    data: bytes,
    start: int,
    expected_script_hash: str,
    *,
    min_satoshis: int | None,
) -> bool:
    script_len = _read_byte(data, start + 8)
    if script_len <= 0:
        return False
    if min_satoshis is not None and _read_amount(data, start) < min_satoshis:
        return False
    script_start = start + 9
    script_bytes = data[script_start:script_start + script_len]
    if len(script_bytes) != script_len:
        return False
    return hashlib.sha256(script_bytes).hexdigest() == expected_script_hash


def _read_amount(data: bytes, start: int) -> int:
    amount = int.from_bytes(data[start:start + 8], "little")
    if amount > MAX_BTC_SATOSHIS:
        raise ValueError("Bitcoin output value exceeds max supply")
    return amount


def _normalize_hex(value: str, *, expected_bytes: int) -> str:
    if not isinstance(value, str):
        raise TypeError("hex value must be a string")
    cleaned = value.strip().lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if len(cleaned) != expected_bytes * 2:
        raise ValueError(f"expected {expected_bytes} bytes")
    bytes.fromhex(cleaned)
    return cleaned


def _validate_satoshis(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > MAX_BTC_SATOSHIS:
        raise ValueError(f"{name} outside Bitcoin supply bounds")
    return value


def _load_proof(path: str | None) -> dict[str, Any]:
    if path in (None, "-"):
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify Ergo context data for Bitcoin tx proofs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a proof JSON object.")
    build.add_argument("--raw-tx", required=True, help="Raw Bitcoin transaction hex.")
    build.add_argument("--output-index", type=int, help="Output index to prove.")
    build.add_argument("--script-hash", help="SHA-256 scriptPubKey hash to prove.")
    build.add_argument("--min-satoshis", type=int, help="Optional minimum output value.")

    verify = subparsers.add_parser("verify-local", help="Verify proof JSON locally.")
    verify.add_argument("proof", nargs="?", default="-", help="Proof JSON path or stdin.")

    args = parser.parse_args(argv)

    if args.command == "build":
        proof = build_bounded_output_proof(
            args.raw_tx,
            output_index=args.output_index,
            script_hash=args.script_hash,
            min_satoshis=args.min_satoshis,
        )
        print(json.dumps(proof, indent=2, sort_keys=True))
        return 0

    if args.command == "verify-local":
        proof = _load_proof(args.proof)
        if proof.get("contract") == "btc_verify_parser_amount":
            ok = verify_bounded_parser_amount(proof)
        else:
            ok = verify_bounded_parser(proof)
        print("ok" if ok else "invalid")
        return 0 if ok else 1

    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
