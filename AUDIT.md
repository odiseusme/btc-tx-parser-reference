# Audit pass — 2026-04-30

A community-driven audit pass on this repository, conducted six weeks after the initial bounty submission. The goal was to surface gaps a future reviewer or production integrator would care about, and to tighten the artifact accordingly.

This audit was prompted by [Degens.world](https://github.com/Degens-World)'s April 29, 2026 community challenge to demonstrate contract auditing via the Ergo Knowledge Base MCP. The work below answers that prompt against a real, mainnet-tested artifact.

Background research was grounded in Ergo community discussions retrieved via the Ergo Knowledge Base MCP ([ergo-knowledge-base.vercel.app](https://ergo-knowledge-base.vercel.app)) — specifically kushti's clarifications of `executeFrom*` semantics in Ergo developer Telegram chats (msg#34571–34572 May 2025; Monthly Summary June 2025) and the broader pattern context from Lithos Protocol's `Evaluation.ergo`.

This audit pass is itself a small proof point for the LLM-assisted contract auditing direction kushti proposed in February 2025 (see Ergo Developer Chat, February 2025).

## Audit dimensions

Six dimensions were evaluated against the contracts and supporting code:

1. **Cryptographic foundations** — `sha256(sha256(...))` txid pattern; the natural-vs-reversed hash convention
2. **R4 + R6 commitment binding** — whether R4 and R6 are bound on-chain or off-chain
3. **Slice / bounds edge cases** — Int overflow, empty slices, empty inputs
4. **SegWit serialization handling** — malleability concerns, witness stripping responsibility
5. **executeFromVar pattern correctness** — does the wiring match kushti's documented semantics
6. **Replay & context binding** — verifier vs. authorizer composition

## Findings

### 1. R4 + R6 binding is off-chain only — by necessity

**Status:** Documented (no patch).

The contract verifies `SHA256(SHA256(rawTx)) == R4` and `SHA256(outputsBytes) == R6` independently. There is no on-chain check that they came from the same Bitcoin transaction. Verifying the binding on-chain would require parsing variable-length input arrays inside the Bitcoin transaction to locate where the outputs section begins — which ErgoScript cannot do, since it lacks unbounded loops over runtime-variable structures.

In a Rosen-Bridge-style use case the box creator (a watcher quorum) is the trust anchor. Off-chain, the quorum agrees on a single canonical Bitcoin transaction and computes both R4 and R6 from it. **Action:** Added "Trust assumptions" section to README making this explicit.

### 2. Bitcoin txid byte order is a usability footgun

**Status:** Patched.

Bitcoin explorers and most libraries display txids in reversed order. R4 stores the natural double-SHA256 output (un-reversed) because ErgoScript has no `.reverse` on `Coll[Byte]`. A user pasting an explorer-format txid into R4 would get silent rejection. **Actions:** Top-level ⚠️ callout added to README; `display_to_natural` and `natural_to_display` helpers added to `btc_tx_parser.py` for one-line conversion.

### 3. SegWit handling is correct and fails closed

**Status:** Documentation confirmed (no patch).

Spender must strip marker/flag/witness for SegWit transactions. If they don't, `sha256(sha256(bytes))` won't match R4 and the contract rejects. Pre-SegWit ECDSA signature malleability is bounded by R4 — only the on-chain transaction's bytes match. Documented correctly; no change needed.

### 4. `scriptLen > 0` defensive check missing

**Status:** Patched.

A zero-length slice produces `sha256("")` — a known constant (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`). If R5 happened to equal that constant, a zero-length slice would verify. Cosmetic in practice but a one-line tightening removes the degenerate edge case. **Action:** Updated `boundsOk` from `scriptLen >= 0` to `scriptLen > 0` in `btc_verify_outputs.ergo`. Recompiled on Ergo mainnet node v6.0.2; new compiled address ends in `...jGrMxfxwexw5QWy3puVDhTYqo2NTLQ2wGDLgCXi`.

### 5. executeFromVar variant — wiring matches kushti's spec, but spend-untested

**Status:** Disclaimer strengthened; spend test open.

The contract's comment states `var(0)` must be serialized via `sigma.serialization.ValueSerializer`, not raw ErgoTree bytes. This matches kushti's own clarification of `executeFrom*` semantics: these functions are macros performing AST substitution from context variables, replacing self and reducing the resulting AST — not function calls over computed arguments. The "untested" disclaimer in the contract was honest and is appropriate.

Closing this gap requires a mainnet spend of a box at the executeFromVar address. The blocker is off-chain tooling: the standard libraries (Fleet SDK, sigma-rust) handle primitive context-extension serialization, but the path to take an arbitrary ErgoScript expression body and produce `ValueSerializer` bytes for `var(0)` is not obvious from public documentation. Lithos Protocol uses this pattern in production but their codebase wasn't yet public as of December 2025. **Action:** STATUS block added to the contract header citing the May/June 2025 kushti clarifications. README "Open work" section spells out what closing this gap requires. Question raised in Ergo developer Telegram.

### 6. No on-chain context binding (verifier vs. authorizer)

**Status:** Documented (no patch).

The contract returns a `sigmaProp` of pure data checks: no signature, no height gate, no box binding. Standalone, anyone holding matching context-extension data can satisfy it. This is intentional — the design intent is composition with an outer authorizer. **Action:** "Composition and authorization" section added to README so integrators don't deploy it raw and assume it's spend-restricted.

## Patches applied in this audit pass

Single commit, four files changed:

| File | Change |
|---|---|
| `btc_verify_outputs.ergo` | `scriptLen > 0` (was `>= 0`); recompiled; new compiled address |
| `btc_verify_executeFromVar.ergo` | Strengthened STATUS block citing kushti's executeFrom* clarifications |
| `btc_tx_parser.py` | Added `display_to_natural` / `natural_to_display` helpers |
| `README.md` | New sections: ⚠️ callout, Trust assumptions, Composition and authorization, Contract evolution, Open work, treeVersion compilation note |

## Open work

**executeFromVar mainnet spend test.** Pending guidance on the cleanest current path to produce `ValueSerializer` bytes for `var(0)` — Scala helper using sigmastate-interpreter directly is the obvious path; sigma-rust or Fleet SDK paths are uncertain.

## Methodology note

This audit was conducted by [odiseusme](https://github.com/odiseusme) in collaboration with Claude (Anthropic) as technical implementation partner, using the [Ergo Knowledge Base MCP](https://ergo-knowledge-base.vercel.app) for community-grounded research. The findings and patches are real but modest in scope — the contracts were already largely sound. The audit's main contribution is making implicit design choices explicit (Trust assumptions, Composition, Contract evolution) so future readers and integrators don't have to reverse-engineer them.
