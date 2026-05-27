# Audit Evidence Matrix

This matrix maps the reference kit's main review questions to concrete
defenses and executable evidence.

| Review question | Defense | Evidence |
| --- | --- | --- |
| Can a Bitcoin explorer txid be accidentally used in R4? | R4 is specified as natural double-SHA256 order; helper functions expose display-to-natural conversion. | `tests/test_reference_kit.py::test_rejects_display_order_txid_in_r4`, `test-vectors/invalid/wrong-r4-display-order.proof.json` |
| Can full SegWit serialization be used where txid-preimage bytes are required? | The contract hashes exactly context var 1; proof builder passes stripped non-witness bytes. | `tests/test_reference_kit.py::test_rejects_full_segwit_raw_bytes_in_context_var`, `test-vectors/invalid/full-segwit-bytes.proof.json` |
| Can an input scriptSig match be confused with an output scriptPubKey match? | R5 is SHA-256 of a parsed output scriptPubKey only. | `tests/test_reference_kit.py::test_rejects_script_hash_that_only_matches_input_script_sig`, `test-vectors/invalid/script-sig-only-match.proof.json` |
| Can malformed bytes with matching txid bypass structural parsing? | The parser checks bounded counts, one-byte CompactSize fields, output ends, and locktime position. | `test_rejects_truncated_transaction_even_with_matching_r4`, `test_rejects_trailing_bytes_even_with_matching_r4`, `test_rejects_unsupported_compactsize_even_with_matching_r4`, `test-vectors/invalid/trailing-byte.proof.json` |
| Can empty scripts be used as a degenerate sha256(empty) match? | `outputMatches` rejects `script_len == 0`. | `test_rejects_empty_script_hash_even_with_matching_r4`, `test-vectors/invalid/empty-script.proof.json` |
| Can amount-bearing proofs ignore value or accept impossible Bitcoin amounts? | The canonical parser is script-hash only; the amount variant binds `R6` to `value_satoshis >= R6` and rejects values above the Bitcoin supply bound. | `test_amount_binding_rejects_underpayment_and_accepts_exact_or_more`, `test_amount_binding_rejects_output_value_above_bitcoin_supply`, `test-vectors/invalid/underpayment.proof.json`, `test-vectors/invalid/oversupply-output.proof.json` |
| Can helper JSON drift from verifier semantics? | All public vectors are loaded by tests; valid vectors must pass and invalid vectors must fail. | `test_valid_json_vectors_verify_locally`, `test_invalid_json_vectors_fail_locally` |
| Can Windows users hit shell-only failures? | CI compiles explicit files and runs unit tests on Ubuntu and Windows. | `.github/workflows/python-tests.yml`, `scripts/check.py` |
| Do the reusable ErgoScript contracts compile outside ad hoc node tooling? | An AppKit test compiles the canonical parser, amount variant, txid verifier, and direct historical verifier contracts. | `src/test/scala/BtcErgoContractsSpec.scala`, `sbt test` |
| Does this prove Bitcoin finality or bridge safety by itself? | Documentation keeps inclusion, finality, authorization, state transitions, duplicate-output policy, and protocol wrapping out of scope. | `THREAT_MODEL.md`, `LIMITATIONS.md`, `SPEC.md` |

The expected local checks are:

```bash
python scripts/check.py
```
