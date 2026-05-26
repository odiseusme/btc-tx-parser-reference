# Test Vectors

The vectors in this directory are small integration fixtures for consumers.

| Path | Expected result | Notes |
| --- | --- | --- |
| `valid/rosen-bridge-output1.proof.json` | accepted | Real Rosen Bridge Bitcoin-to-Ergo SegWit transaction after witness stripping |
| `invalid/wrong-r4-display-order.proof.json` | rejected | R4 uses Bitcoin display-order txid instead of natural double-SHA256 bytes |
| `invalid/full-segwit-bytes.proof.json` | rejected | Context var 1 contains full SegWit bytes instead of stripped txid-preimage bytes |
| `invalid/script-sig-only-match.proof.json` | rejected | R5 matches an input scriptSig hash, not an output scriptPubKey hash |
| `invalid/trailing-byte.proof.json` | rejected | R4 matches the supplied bytes, but the structural locktime check rejects trailing data |
| `invalid/empty-script.proof.json` | rejected | Empty scriptPubKey cannot satisfy the output-match predicate |

`tests/test_reference_kit.py` loads every `*.proof.json` file from both
directories. This keeps public vectors and local verifier behavior in sync.
