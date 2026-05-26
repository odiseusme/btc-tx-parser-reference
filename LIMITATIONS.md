# Limitations

This repository is intentionally narrow.

## No Bitcoin Inclusion Proof

The parser verifies transaction bytes against a txid. It does not prove that the
transaction is in a Bitcoin block, in the best chain, or confirmed by any number
of blocks.

To make a trust-minimized Bitcoin-to-Ergo claim, compose this parser with a
Bitcoin header, Merkle inclusion, and finality proof layer.

## Bounded Parser Only

The canonical parser is not a full Bitcoin parser. It accepts only:

- non-witness serialization;
- single-byte CompactSize fields;
- 1 or 2 inputs;
- 1 to 4 outputs.

This is a feature, not a bug. The contract should be small, explicit, and
auditable.

## Script Hash Membership Is Not UTXO Identity

`btc_verify_parser.ergo` proves that some parsed output has a matching script
hash. It does not bind:

- output index;
- output value;
- uniqueness of that script within the transaction.

Add protocol-level rules when amount, index, uniqueness, or duplicate-output
policy matters.

## executeFromVar Variant Status

`btc_verify_executeFromVar.ergo` is a supplementary historical exploration.
The reproducible AppKit CI compile harness intentionally covers the canonical
parser and the earlier direct verifier contracts, but not this executeFromVar
variant.

## Pure Verifier, Not Authorizer

The contracts in this repository check public facts. They do not require a
signature, enforce an Ergo payout, preserve tokens, or advance a state machine.
Any production protocol must wrap the verifier with the necessary Ergo-side
authorization and state transition checks.

## Byte Order Footgun

Bitcoin explorer txids are display-order values. `R4` requires natural
double-SHA256 byte order. Use the helper functions in `btc_tx_parser.py`.
