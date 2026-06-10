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
| `invalid/underpayment.proof.json` | rejected | Amount-binding contract rejects a matching output below the R6 minimum |
| `invalid/oversupply-output.proof.json` | rejected | Amount-binding contract rejects an output value above the Bitcoin supply bound |
| `valid/oversupply-sibling-output.proof.json` | accepted | Over-supply value on a non-target output is a per-output non-match; the other output still satisfies script hash and R6 minimum |

`tests/test_reference_kit.py` loads every `*.proof.json` file from both
directories. This keeps public vectors and local verifier behavior in sync.
