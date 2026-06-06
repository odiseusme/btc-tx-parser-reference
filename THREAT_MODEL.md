# Threat Model

This repository verifies bounded Bitcoin transaction facts. It does not
authorize production spending by itself.

## Assets At Risk

If composed into a production protocol, the protected assets may be:

- Ergo boxes unlocked after a Bitcoin payment;
- tokens, NFTs, licenses, or claims released by an Ergo state machine;
- bridge or escrow state that reacts to Bitcoin events.

## Trusted Inputs

For the parser layer only:

- the box creator chooses `R4`, `R5`, and optionally `R6`;
- the spender supplies transaction bytes through context var `1`;
- the contract verifies consistency between those values.

For a trust-minimized Bitcoin claim, a separate layer must authenticate Bitcoin
block inclusion and finality. This repository does not do that.

## Adversary Capabilities

Assume an adversary can:

- provide arbitrary context-extension bytes;
- choose malformed Bitcoin transaction bytes;
- use explorer-display txid byte order instead of natural byte order;
- include matching script bytes inside an input `scriptSig`;
- append trailing bytes;
- truncate the transaction;
- use unsupported CompactSize forms;
- attempt zero-length scripts;
- create several outputs with the same script but different amounts;
- satisfy a pure verifier and spend any standalone verifier box.

## Required Security Properties

The canonical parser should:

- bind `R4` to the exact supplied non-witness transaction bytes;
- parse outputs structurally, not by user-supplied offsets;
- reject script matches that occur only in inputs;
- reject zero-length scripts;
- reject transaction shapes outside the bounded subset;
- reject trailing or truncated bytes;
- fail closed on malformed data.

The amount variant should additionally:

- compare only Bitcoin output values that fit within the Bitcoin supply bound;
- reject negative or over-supply `R6` thresholds;
- accept exact or greater output values;
- reject underpayment.

## Out Of Scope

These are not covered by the parser:

- Bitcoin header validation;
- Bitcoin transaction Merkle inclusion;
- proof-of-work best-chain selection;
- confirmation depth;
- Bitcoin script execution;
- current UTXO spendability;
- wallet UX, payment monitoring, or mempool handling.

## Production Composition Rules

Do not fund a standalone parser contract as if it were an escrow. A pure parser
box is spendable by anyone who can provide matching public transaction bytes.

Production use needs an outer protocol that authenticates:

- who may spend;
- which Ergo output receives value or assets;
- how state advances;
- whether Bitcoin inclusion/finality evidence is sufficient;
- whether duplicate Bitcoin outputs are acceptable;
- whether the amount threshold is sufficient for the business action.
