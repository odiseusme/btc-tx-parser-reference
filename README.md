# Bitcoin Output Commitment Verification in ErgoScript

Reference implementation for [ergoplatform/sigmastate-interpreter#1114](https://github.com/ergoplatform/sigmastate-interpreter/issues/1114).

This repository shows a practical ErgoScript pattern for verifying Bitcoin transaction data on-chain, including proof that a target script belongs to the **outputs section** of the Bitcoin transaction.

## What problem this solves

Suppose an Ergo box stores:

- `R4` — a Bitcoin txid
- `R5` — the hash of a Bitcoin output script
- `R6` — the hash of the Bitcoin transaction's outputs section

The box should be spendable only when the prover supplies Bitcoin transaction data showing that:

1. the transaction matches `R4`
2. the outputs section matches `R6`
3. the claimed script bytes are inside that outputs section
4. those script bytes hash to `R5`

This repository demonstrates that pattern.

## Why R6 is needed

A simpler `R4 + R5` design is not enough.

If the contract only checks that the transaction bytes match the txid and some byte slice hashes to the expected script, it proves only that matching bytes exist somewhere inside the transaction bytes. As identified during review, those bytes could appear inside an input `ScriptSig` (via `OP_PUSH`) rather than in an output `scriptPubKey`.

The revised design fixes this by adding `R6`, a commitment to the Bitcoin outputs section itself.

## What's here

**`btc_tx_parser.py`** — Python reference parser for Bitcoin transactions. Handles legacy and SegWit forms. Produces Bitcoin display txid, natural-order txid for R4, stripped transaction bytes, extracted outputs section bytes for R6, and relative offsets of each output scriptPubKey within the outputs section.

**`btc_verify_outputs.ergo`** — Main ErgoScript contract (hardened). Verifies R4 (txid), R6 (outputs section commitment), bounds checks, and R5 (script hash within committed outputs section). Compiled address: `5f57sYY6AuoxSubXYsEJburtFXcyLTGJV6hK9X9zVLS8Yeq3o4439nN7cUAJc6b159og3sWAsCSM3r1iHhdnE7PdWVkibmuZs5VkfXdZGKoRaD2S9CYHv7zP6QcXqWGTPjx3`

**`btc_verify_full.ergo`** — Earlier baseline using only R4 + R5. Included for comparison. Not the recommended pattern.

**`btc_txid_verify.ergo`** — Minimal txid-only verifier. Building block.

**`btc_verify_executeFromVar.ergo`** — Optional supplementary refactor using `executeFromVar`.

**`test_rosen_bridge.py`** — Verifies the parser against a real Rosen Bridge Bitcoin→Ergo SegWit transaction (0.003 BTC, Sep 2025). Tests both baseline and hardened contract flows.

## How it works

Bitcoin transaction bytes are parsed off-chain. The prover supplies to ErgoScript:

1. Stripped Bitcoin transaction bytes (var 1)
2. Relative script offset within outputs section (var 2)
3. Script length (var 3)
4. Outputs section bytes (var 4)

The contract verifies:

1. **Txid check** — `SHA256(SHA256(stripped_tx_bytes)) == R4`
2. **Outputs section commitment** — `SHA256(outputs_section_bytes) == R6`
3. **Bounds check** — offset and length define a valid slice inside the outputs section
4. **Script hash check** — `SHA256(outputs_section_bytes[offset:offset+len]) == R5`

This proves the matched script bytes are inside the committed outputs section, not merely somewhere inside the Bitcoin transaction.

## Register conventions

- `R4` = Bitcoin txid in natural double-SHA256 byte order
- `R5` = expected Bitcoin output script hash (SHA256)
- `R6` = SHA256 hash of Bitcoin outputs section bytes

## Important notes

**Txid byte order:** Bitcoin explorers display txids reversed. R4 stores the natural hash order because ErgoScript doesn't support `.reverse` on `Coll[Byte]`. Do not copy a txid from an explorer into R4 without converting.

**SegWit:** The contract uses stripped serialization (no marker/flag/witness) because Bitcoin txid is defined over the non-witness serialization.

**Limitations:** This does not implement a full Bitcoin parser inside ErgoScript. It uses off-chain parsing with on-chain verification of cryptographic commitments strong enough to prove outputs-section membership.

## Mainnet verification

Both the baseline and hardened contracts have been tested on Ergo mainnet:

- Baseline (txid only): contract box spent at block 1,763,199. Tx: `0ede5f0d3cd543b0a3f5f2c1872bb62a13dd64f573ee5ac06350007674d5cd69`
- Hardened (R4+R5+R6): contract box spent at block 1,763,772. Tx: `49fc760609080786010bdd91929ef8853d12da3fa3846a3351044170fe78d8e6`

## Run the tests

```bash
python3 btc_tx_parser.py          # Parse Satoshi → Hal Finney tx
python3 test_rosen_bridge.py      # Parse real Rosen Bridge tx + outputs section
```

## ErgoScript contracts

All compiled on Ergo mainnet node v6.0.2:

| File | What it does | Status |
|------|-------------|--------|
| `btc_verify_outputs.ergo` | Hardened: R4 + R5 + R6 outputs commitment | **Recommended** |
| `btc_verify_full.ergo` | Baseline: R4 + R5 only | Historical |
| `btc_txid_verify.ergo` | Txid only (R4) | Building block |
| `btc_verify_executeFromVar.ergo` | executeFromVar variant | Supplementary |

## Context

Built by [odiseusme](https://github.com/odiseusme) in collaboration with Claude (Anthropic) as technical implementation partner. See [issue #1114](https://github.com/ergoplatform/sigmastate-interpreter/issues/1114) for the original bounty.
