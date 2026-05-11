# Bitcoin Output Commitment Verification in ErgoScript

Reference implementation for [ergoplatform/sigmastate-interpreter#1114](https://github.com/ergoplatform/sigmastate-interpreter/issues/1114).

This repository shows a practical ErgoScript pattern for verifying Bitcoin transaction data on-chain, including proof that a target script belongs to the **outputs section** of the Bitcoin transaction.

> ⚠️ **Bitcoin txid byte order.** Bitcoin explorers and most libraries display txids reversed from their natural double-SHA256 byte order. Register `R4` in this contract stores the **natural** order (the raw `SHA256(SHA256(tx_bytes))` output), not the explorer-display order. Copying a txid from an explorer directly into `R4` will not work. The Python parser in `btc_tx_parser.py` produces both forms.

> 📅 **Update — 2026-05-11.** After community feedback (Kushti, Ergo dev Telegram, 2026-04-30) that an outputs-section hash is not a Bitcoin-native primitive, this repository has been extended with `btc_verify_parser.ergo` — a bounded structural parser that proves output-section membership from the authenticated transaction bytes themselves, without an R6 helper commitment. The parser is the canonical answer to #1114 as of this date. The R6-based `btc_verify_outputs.ergo` is retained as evolution history. See [Post-pivot status](#post-pivot-status--2026-05-11) below.

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

**`btc_verify_parser.ergo`** — Bounded structural parser (the canonical answer to #1114 after the 2026-05-11 pivot). Verifies R4 (txid) and R5 (one parsed output's scriptPubKey hash) by walking the transaction structure within a bounded subset: 1-2 inputs, 1-4 outputs, single-byte CompactSize encoding (values < 0xfd), non-witness serialization. Locktime structural anchor (outputsEnd == size - 4) prevents drift. No R6 helper commitment; output-section membership is proven structurally from the authenticated bytes.

**`btc_verify_outputs.ergo`** — Earlier hardened contract (R4+R5+R6 with outputs-section commitment). Retained as evolution history. Verifies R4 (txid), R6 (outputs section commitment), bounds checks, and R5 (script hash within committed outputs section). Compiled address: `5f57sYY6AuoxSubXYsEJburtFXcyLTGJV6hK9X9zVLS8Yeq3o4439nN7cUAJc6b159og3sWAsCSM3r1iHhdnE7PdWVkibjGrMxfxwexw5QWy3puVDhTYqo2NTLQ2wGDLgCXi`

**`btc_verify_full.ergo`** — Earlier baseline using only R4 + R5. Included for narrative completeness — this is the version Kushti's review identified as inadequate (see "Contract evolution" below). Not the recommended pattern; do not use it in production.

**`btc_txid_verify.ergo`** — Minimal txid-only verifier. Building block.

**`btc_verify_executeFromVar.ergo`** — Optional supplementary refactor using `executeFromVar`. Compiled on mainnet but **not yet spend-tested** — see "Open work" below.

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
3. **Bounds check** — offset and length define a valid non-empty slice inside the outputs section
4. **Script hash check** — `SHA256(outputs_section_bytes[offset:offset+len]) == R5`

This proves the matched script bytes are inside the committed outputs section, not merely somewhere inside the Bitcoin transaction.

## Register conventions

- `R4` = Bitcoin txid in natural double-SHA256 byte order
- `R5` = expected Bitcoin output script hash (SHA256)
- `R6` = SHA256 hash of Bitcoin outputs section bytes

## Trust assumptions

This contract enforces self-consistency of what each box claims, but it does not — and cannot in pure ErgoScript — enforce structural binding between `R4` and `R6` on-chain.

Concretely: the script verifies `SHA256(SHA256(rawTx)) == R4` and `SHA256(outputsBytes) == R6` independently. If the box creator placed a txid from transaction A in `R4` and an outputs-section hash from a different transaction B in `R6`, the contract has no way to detect the mismatch. Verifying the binding on-chain would require parsing variable-length input arrays inside the Bitcoin transaction to locate where the outputs section begins — which ErgoScript cannot do, since it lacks unbounded loops over runtime-variable structures.

In a Rosen-Bridge-style use case, the box creator (a watcher quorum) is the trust anchor. Off-chain, the quorum agrees on a single canonical Bitcoin transaction and computes both `R4` and `R6` from it. Integrators are responsible for ensuring `R4` and `R6` come from the same source transaction at box construction time.

## Composition and authorization

The contract is a **verifier**, not an **authorizer**. It returns a `sigmaProp` of pure data checks: no signature, no height gate, no spender identity, no box binding beyond what's in the registers. Anyone holding matching context-extension data can satisfy it.

This is intentional. The pattern is meant to be composed with an outer authorizer — for example, an `AND` with a Schnorr signature, a height gate, or a multi-input contract that requires another box's spending conditions to also be met. Deploying this contract standalone gives you a "fact certificate": once funded, anyone can produce the witness to spend it. That is rarely what you want in production. Wrap it.

## Contract evolution

| Stage | File | What it proves | Notes |
|---|---|---|---|
| 1 | `btc_txid_verify.ergo` | Txid only (R4) | Minimal building block |
| 2 | `btc_verify_full.ergo` | Txid + script hash (R4+R5) | Pre-review version. Kushti identified that a matching slice could come from a `ScriptSig` rather than an output `scriptPubKey`. Superseded. |
| 3 | `btc_verify_outputs.ergo` | Txid + outputs commitment + script hash (R4+R5+R6) | Hardened post-review. Mainnet-tested. Superseded 2026-05-11 — see stage 4. |
| 4 | `btc_verify_parser.ergo` | Txid + script hash via bounded structural parsing (R4+R5) | Pivoted to after Kushti's 2026-04-30 critique that the R6 outputs-section hash is not a Bitcoin-native primitive. Proves output-section membership structurally rather than via helper commitment. **Canonical version.** Mainnet-tested. |
| supp | `btc_verify_executeFromVar.ergo` | R4+R5 with verification logic moved off-chain into `var(0)` | Pattern from Lithos Protocol. Compiled, not spend-tested. Deprioritized after pivot — not the canonical answer to #1114. |

## Important notes

**SegWit:** The contract uses stripped serialization (no marker/flag/witness) because Bitcoin txid is defined over the non-witness serialization. The Python parser strips automatically.

**Compilation:** Compiled on Ergo node v6.0.2. ErgoTree v6 introduced explicit version selection — the `/script/p2sAddress` endpoint requires a `treeVersion` field in the request body (use `0` for current default). Pre-v6 nodes did not require this field.

**No full Bitcoin parser inside ErgoScript:** Off-chain parsing combined with on-chain verification of cryptographic commitments. The commitments are strong enough to prove outputs-section membership; full structural parsing is impractical in current ErgoScript.

## Mainnet verification

Two contracts have been spend-tested on Ergo mainnet:

| Contract | Block | Spend tx |
|---|---|---|
| `btc_txid_verify.ergo` (baseline, R4 only) | 1,763,199 | `0ede5f0d3cd543b0a3f5f2c1872bb62a13dd64f573ee5ac06350007674d5cd69` |
| `btc_verify_outputs.ergo` (hardened, R4+R5+R6) | 1,763,772 | `49fc760609080786010bdd91929ef8853d12da3fa3846a3351044170fe78d8e6` |
| `btc_verify_parser.ergo` (bounded structural parser, R4+R5) | 1,776,872 | `4298f96593ec179e8aa364efdede4ff5ad7f08d0d9bdc9562f78ee288cdb9129` |

`btc_verify_full.ergo` was superseded before spend-testing (see "Contract evolution"). `btc_verify_executeFromVar.ergo` is deprioritized after the 2026-05-11 pivot — see [Post-pivot status](#post-pivot-status--2026-05-11) below.

## Post-pivot status — 2026-05-11

On 2026-04-30 (Ergo developer Telegram), Kushti raised a substantive concern about the R6 outputs-section hash approach: an outputs-section hash is not a Bitcoin-native primitive — Bitcoin's consensus commits to txids (which are double-SHA256 of the transaction bytes), but it does not commit to "the hash of the outputs section" as a separate value. There is no canonical SPV-style proof that a given byte region is the outputs section of a given Bitcoin transaction. The R6 helper in `btc_verify_outputs.ergo` is a valid intra-claim consistency check but cannot be anchored to Bitcoin's chain state.

This drove a pivot to `btc_verify_parser.ergo`: a bounded structural parser that proves output-section membership directly from the authenticated Bitcoin transaction bytes, without a helper commitment. The parser walks the transaction structure (version, input count, inputs, output count, outputs, locktime) within a documented bounded subset (1-2 inputs, 1-4 outputs, single-byte CompactSize, non-witness serialization). Transactions outside this subset are explicitly rejected, not silently mishandled. The locktime structural anchor (`outputsEnd == size - 4`) prevents structural drift.

The parser was reviewed via the Ergo Knowledge Base MCP audit tool (`audit_contract` Pass 1 returned no findings at any severity) and mainnet-verified at block 1,776,872, spend tx `4298f96593ec179e8aa364efdede4ff5ad7f08d0d9bdc9562f78ee288cdb9129`.

The Trust Assumptions section above remains accurate for `btc_verify_outputs.ergo` (R4↔R6 binding is off-chain only). It does not apply to `btc_verify_parser.ergo`, which proves output-section membership structurally from the bytes the txid commitment in R4 already authenticates.

`btc_verify_executeFromVar.ergo` was a parallel exploration. After the pivot it is no longer the canonical answer to #1114, and the spend test that was previously listed as open work is deprioritized. The contract remains in the repository as historical reference. The off-chain serialization recipe is now well-understood (the canonical pattern is `ValueSerializer.serialize(ergoTree.toProposition(true))` inside `VersionContext.withVersions(V6SoftForkVersion, V6SoftForkVersion)` — see Lithos-Protocol/Lithos-Client `lithos-lib/src/main/scala/mutations/Contract.scala` for the production reference), but proving it on mainnet is not necessary for the bounty answer.

## Run the tests

```bash
python3 btc_tx_parser.py          # Parse Satoshi → Hal Finney tx
python3 test_rosen_bridge.py      # Parse real Rosen Bridge tx + outputs section
```

## ErgoScript contracts

All compiled on Ergo mainnet node v6.0.2:

| File | What it does | Status |
|------|-------------|--------|
| `btc_verify_parser.ergo` | Bounded structural parser: R4 + R5 via on-chain parsing | **Canonical, mainnet-tested (block 1,776,872)** |
| `btc_verify_outputs.ergo` | Hardened: R4 + R5 + R6 outputs commitment | Mainnet-tested (block 1,763,772). Superseded 2026-05-11 — see Post-pivot status |
| `btc_txid_verify.ergo` | Txid only (R4) | Building block, mainnet-tested |
| `btc_verify_full.ergo` | Baseline: R4 + R5 only | Pre-review, superseded |
| `btc_verify_executeFromVar.ergo` | executeFromVar variant | Compiled, spend-test deprioritized after pivot |

## Context

Built by [odiseusme](https://github.com/odiseusme) in collaboration with Claude (Anthropic) as technical implementation partner. See [issue #1114](https://github.com/ergoplatform/sigmastate-interpreter/issues/1114) for the original bounty.
