# Bitcoin Transaction Proofs For ErgoScript

Reference implementation for
[ergoplatform/sigmastate-interpreter#1114](https://github.com/ergoplatform/sigmastate-interpreter/issues/1114).

This repository shows how an Ergo contract can verify a bounded fact about
Bitcoin transaction bytes:

> These non-witness Bitcoin transaction bytes hash to the expected txid, and at
> least one parsed output has the expected scriptPubKey hash.

The current canonical contract is `btc_verify_parser.ergo`. It proves output
membership by structurally walking the authenticated transaction bytes. Earlier
R6 outputs-section helper contracts remain in the repository as history, not as
the recommended pattern.

## Status

| File | Status | Purpose |
| --- | --- | --- |
| `btc_verify_parser.ergo` | Canonical, mainnet spend-tested | R4 txid + R5 parsed output script hash |
| `btc_verify_parser_amount.ergo` | Canonical, mainnet spend-tested | R4 txid + R5 script hash + R6 minimum satoshis |
| `btc_ergo_proof.py` | Tested helper | Build and locally verify proof JSON |
| `btc_tx_parser.py` | Tested helper | Parse Bitcoin transactions and strip SegWit witness data |
| `btc_verify_outputs.ergo` | Historical | R4 + R5 + R6 outputs-section helper hash |
| `btc_verify_full.ergo` | Historical unsafe baseline | R4 + R5 arbitrary slice |
| `btc_txid_verify.ergo` | Building block | Txid-only verification |
| `btc_verify_executeFromVar.ergo` | Supplementary historical variant | executeFromVar exploration |

## Quick Start

Run the parser examples:

```bash
python btc_tx_parser.py
python test_rosen_bridge.py
```

Run the test suite:

```bash
python scripts/check.py
```

Build a proof JSON object:

```bash
python btc_ergo_proof.py build --raw-tx <raw_tx_hex> --output-index 1
```

Verify a proof JSON object locally:

```bash
python btc_ergo_proof.py verify-local test-vectors/valid/rosen-bridge-output1.proof.json
```

## What The Canonical Parser Proves

For `btc_verify_parser.ergo`, the box and context ABI is:

| Location | Type | Meaning |
| --- | --- | --- |
| `SELF.R4` | `Coll[Byte]` | Bitcoin txid in natural double-SHA256 byte order |
| `SELF.R5` | `Coll[Byte]` | `SHA256(scriptPubKey)` for the target output script |
| `getVar(1)` | `Coll[Byte]` | Non-witness Bitcoin transaction bytes |

The contract checks:

1. `sha256(sha256(txBytes)) == R4`
2. transaction structure fits the bounded subset;
3. one parsed output has `sha256(scriptPubKey) == R5`;
4. locktime lands exactly at the end of the parsed outputs.

## Amount-Binding Variant

`btc_verify_parser_amount.ergo` extends the canonical ABI with:

| Location | Type | Meaning |
| --- | --- | --- |
| `SELF.R6` | `Long` | Minimum required output value in satoshis |

It proves that one parsed output has both the expected script hash and
`value_satoshis >= R6`. This is the natural next primitive for "pay BTC, claim
on Ergo" flows. It was mainnet spend-tested at block `1,805,269` with `R6` set
to the matched output's exact satoshi value, exercising the `>=` boundary
on-chain (see Mainnet Evidence).

## Supported Bitcoin Transaction Shape

The bounded parser accepts only:

- non-witness serialization only;
- single-byte CompactSize counts and script lengths (`< 0xfd`);
- 1 or 2 inputs;
- 1 to 4 outputs;
- non-empty output scripts;
- no trailing bytes before or after locktime.

Transactions outside this subset are rejected. This is intentional. ErgoScript
has no unbounded loops over runtime-variable Bitcoin transaction structure, so a
small explicit parser is safer than implying full Bitcoin parser support.

## What This Does Not Prove

This repository does not prove:

- Bitcoin block inclusion;
- Bitcoin finality or confirmations;
- best-chain selection;
- current UTXO spendability;
- full Bitcoin script execution;
- support for every valid Bitcoin transaction shape;
- authorization to spend a production Ergo box.

The parser is a verifier, not an authorizer. Production designs must compose it
with signatures, state-machine checks, token rules, height/finality policy, and
a separate Bitcoin inclusion/finality layer when trust minimization requires it.

See:

- [SPEC.md](SPEC.md)
- [THREAT_MODEL.md](THREAT_MODEL.md)
- [LIMITATIONS.md](LIMITATIONS.md)
- [AUDIT_EVIDENCE.md](AUDIT_EVIDENCE.md)
- [CHECKS.md](CHECKS.md)

## Bitcoin Txid Byte Order

Bitcoin explorers and most libraries display txids reversed from their natural
double-SHA256 byte order. Register `R4` stores the natural order, the raw
`SHA256(SHA256(tx_bytes))` output.

Use:

```python
from btc_tx_parser import display_to_natural, natural_to_display
```

Copying a displayed explorer txid directly into `R4` will fail.

## Test Coverage

The Python tests cover:

- valid Rosen Bridge SegWit fixture after witness stripping;
- proof JSON generation and local verification;
- wrong txid byte order;
- full SegWit bytes passed instead of stripped bytes;
- target script hash appearing only in `scriptSig`;
- truncated bytes;
- trailing bytes;
- more than four outputs;
- empty output script;
- unsupported CompactSize marker;
- amount threshold pass/fail behavior;
- public valid and invalid JSON vectors;
- AppKit compilation of the canonical contracts;

## Mainnet Evidence

The canonical parser was reported as mainnet spend-tested at block `1,776,872`,
spend transaction:

`4298f96593ec179e8aa364efdede4ff5ad7f08d0d9bdc9562f78ee288cdb9129`

The amount-binding variant was mainnet spend-tested at block `1,805,269`,
spend transaction:

`967d10f6f331bd15771d991a1e42f09fc0dbb671472e7c7a7cefae63274d45c8`

The funding box carried R4/R5 from the same Rosen Bridge Bitcoin transaction
used throughout the public vectors, with `R6 = 300000` — the matched output's
exact value, so the spend exercised the `value >= R6` boundary case.
First-try success, no failed spends.

Earlier historical contracts were also spend-tested and remain documented in
`AUDIT.md`.

## Repository Context

Built by [odiseusme](https://github.com/odiseusme) for Ergo issue #1114. This
repository is a reference artifact, not a consensus-standard Bitcoin parser and
not a complete Bitcoin-to-Ergo bridge.
