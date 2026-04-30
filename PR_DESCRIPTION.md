# PR: Bitcoin transaction output commitment verification in ErgoScript — Issue #1114

## Summary

This PR provides a practical ErgoScript example for verifying Bitcoin transaction data on-chain, revised after review to ensure that the claimed script bytes are proven to be inside the **outputs section** of the Bitcoin transaction. The repository was subsequently audit-tightened on 2026-04-30 (see [AUDIT.md](AUDIT.md)).

The original baseline approach verified that the transaction bytes matched the txid and that a selected byte slice hashed to the expected script hash. However, as pointed out during review, this only proved that matching bytes existed somewhere inside the authenticated transaction bytes — the same bytes could appear in an input `ScriptSig` rather than in an output `scriptPubKey`.

The revised version fixes this by adding a separate commitment to the Bitcoin outputs section:

- `R4` = Bitcoin txid in natural double-SHA256 order
- `R5` = expected Bitcoin output script hash
- `R6` = SHA256 hash of the Bitcoin outputs section bytes

At spending time, the prover supplies the stripped Bitcoin transaction bytes, the outputs section bytes, and the relative offset and length of the target script within the outputs section.

## What's included

### Core ErgoScript contract (`btc_verify_outputs.ergo`) — main submission

Verifies:
1. `SHA256(SHA256(stripped_tx_bytes)) == R4`
2. `SHA256(outputs_section_bytes) == R6`
3. bounds checks on offset and length within outputs section (`scriptLen > 0`, tightened in 2026-04-30 audit)
4. `SHA256(outputs_section_bytes[offset:offset+len]) == R5`

Compiled on Ergo mainnet node v6.0.2.
Address: `5f57sYY6AuoxSubXYsEJburtFXcyLTGJV6hK9X9zVLS8Yeq3o4439nN7cUAJc6b159og3sWAsCSM3r1iHhdnE7PdWVkibjGrMxfxwexw5QWy3puVDhTYqo2NTLQ2wGDLgCXi`

### Pre-review snapshot (`btc_verify_full.ergo`) — superseded

Simpler R4 + R5 approach. Retained for explanatory value as the "before" version that Kushti's review identified as inadequate. **Not the recommended pattern; not for production use.**

### Building block (`btc_txid_verify.ergo`)

Txid-only verification via double-SHA256.

### Supplementary (`btc_verify_executeFromVar.ergo`)

executeFromVar variant. Compiled on mainnet but **not yet spend-tested**. The off-chain `ValueSerializer` serialization path remains the open piece of work. See "Open work — testing the executeFromVar variant" in the README.

### Python reference parser (`btc_tx_parser.py`)

Off-chain component that parses raw Bitcoin transactions (legacy + SegWit), outputs txid in both formats, strips SegWit witness data, extracts the outputs section bytes and its hash, and computes relative script offsets within the outputs section. Includes `display_to_natural` / `natural_to_display` helpers (added 2026-04-30) for converting explorer-format txids to the natural-order form expected by R4.

### Test (`test_rosen_bridge.py`)

Verified against a real Rosen Bridge Bitcoin→Ergo SegWit transaction (0.003 BTC, Sep 2025). Tests both pre-review and hardened flows with round-trip offset verification.

## Design decisions

**Why R6:** Review identified that proving "matching bytes somewhere in the transaction" is not enough. Adding R6 as a commitment to the outputs section is the smallest practical repair that makes output membership provable on-chain under current ErgoScript constraints.

**Off-chain R4↔R6 binding:** The contract verifies R4 and R6 independently; the binding that they describe the same Bitcoin transaction is enforced off-chain at box construction time (e.g., by a watcher quorum). Structural binding on-chain would require parsing variable-length Bitcoin input arrays, which ErgoScript cannot do without unbounded loops. See README "Trust assumptions" section.

**Verifier vs. authorizer:** The contract is a pure verifier — no signature, no height gate, no spender identity binding. Production deployments should compose it with an outer authorizer (Schnorr signature, height gate, multi-input contract). See README "Composition and authorization" section.

**Natural hash order for R4:** ErgoScript doesn't support `.reverse` on `Coll[Byte]`. R4 stores the raw double-SHA256 output without reversing.

**SegWit handling:** Context variables use the stripped (txid-preimage) serialization because Bitcoin txid is defined over the non-witness serialization.

**No full in-script parser:** Bitcoin transactions contain multiple variable-length fields. A full structural parser is impractical in ErgoScript. The design keeps parsing off-chain while using cryptographic commitments to prove outputs-section membership on-chain.

## Testing status

- [x] Python parser verified against Satoshi→Hal Finney tx
- [x] Python parser verified against real Rosen Bridge Bitcoin→Ergo transaction
- [x] All ErgoScript contracts compile on Ergo mainnet node v6.0.2
- [x] Outputs section extraction and relative offsets verified
- [x] Pre-review baseline mainnet spend: block 1,763,199 (`0ede5f0d3cd543b0a3f5f2c1872bb62a13dd64f573ee5ac06350007674d5cd69`)
- [x] Hardened mainnet spend: block 1,763,772 (`49fc760609080786010bdd91929ef8853d12da3fa3846a3351044170fe78d8e6`)
- [x] Audit pass 2026-04-30 — see [AUDIT.md](AUDIT.md)
- [ ] executeFromVar variant mainnet spend test — open, blocked on `ValueSerializer` off-chain tooling

## Repository

https://github.com/odiseusme/btc-tx-parser-reference

## Context

This contribution was prepared in response to issue #1114, which asked for an example of Bitcoin transaction parsing/verification in ErgoScript. The final version is specifically revised after review feedback to ensure that the matched script bytes are proven to belong to the Bitcoin outputs section. Built in collaboration with Claude (Anthropic) as technical implementation partner.
