# Specification

This specification defines the current reusable proof shape for verifying
bounded Bitcoin transaction facts inside Ergo contracts.

## Proof Classes

### `btc_verify_parser`

Verifies:

1. supplied non-witness Bitcoin transaction bytes hash to `SELF.R4`;
2. the transaction fits the bounded parser subset;
3. at least one parsed output has `SHA256(scriptPubKey) == SELF.R5`.

ABI:

| Location | Type | Meaning |
| --- | --- | --- |
| `SELF.R4` | `Coll[Byte]` | Natural-order double-SHA256 txid |
| `SELF.R5` | `Coll[Byte]` | SHA-256 of target output `scriptPubKey` |
| `getVar(1)` | `Coll[Byte]` | Non-witness transaction bytes |

### `btc_verify_parser_amount`

Adds amount binding for payment-style claims.

ABI:

| Location | Type | Meaning |
| --- | --- | --- |
| `SELF.R4` | `Coll[Byte]` | Natural-order double-SHA256 txid |
| `SELF.R5` | `Coll[Byte]` | SHA-256 of target output `scriptPubKey` |
| `SELF.R6` | `Long` | Minimum required output value in satoshis |
| `getVar(1)` | `Coll[Byte]` | Non-witness transaction bytes |

Verifies all `btc_verify_parser` conditions plus:

```text
parsed_output.value_satoshis >= R6
0 <= R6 <= 2100000000000000
parsed_output.value_satoshis <= 2100000000000000
```

## Transaction Subset

The parser accepts:

- non-witness serialization only;
- one-byte CompactSize values only (`< 0xfd`);
- 1 or 2 inputs;
- 1 to 4 outputs;
- output script lengths greater than zero;
- a locktime structural anchor where parsed outputs end exactly at
  `txBytes.size - 4`.

It rejects everything else.

## Proof JSON

`btc_ergo_proof.py build` emits:

```json
{
  "version": "btc-ergo-proof-v1",
  "contract": "btc_verify_parser",
  "bitcoin": {
    "txid_display": "...",
    "txid_natural": "...",
    "is_segwit": true,
    "input_count": 1,
    "output_count": 3,
    "stripped_size_bytes": 175
  },
  "registers": {
    "R4": "...",
    "R5": "..."
  },
  "context": {
    "1": "..."
  },
  "selected_output": {
    "index": 1,
    "value_satoshis": 300000,
    "script_pubkey_hex": "...",
    "script_hash_sha256": "..."
  }
}
```

For the amount variant, `contract` is `btc_verify_parser_amount` and
`registers.R6` is the minimum satoshi threshold.

Public proof vectors live under `test-vectors/valid` and
`test-vectors/invalid`. The test suite loads every `*.proof.json` vector and
checks that valid vectors pass while invalid vectors fail.

## Byte Order

`R4` uses natural double-SHA256 byte order. Bitcoin explorer display order is
the reverse of this value. `R5` is a single SHA-256 over the exact
`scriptPubKey` bytes.

## Failure Semantics

Malformed transactions should fail closed. In ErgoScript, out-of-bounds reads
invalidate the spend. In the Python local verifier, malformed inputs return
`False`.
