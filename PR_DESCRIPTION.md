# PR: Reference-kit hardening for Bitcoin transaction proofs in ErgoScript

## Summary

This updates the #1114 reference artifact around the bounded structural parser
as the canonical implementation.

The main goal is to make the primitive easier to review and reuse:

- puts `btc_verify_parser.ergo` first in the README;
- documents the ABI in `SPEC.md`;
- adds `THREAT_MODEL.md` and `LIMITATIONS.md`;
- adds a proof-builder/local-verifier CLI (`btc_ergo_proof.py`);
- adds unit tests and Ubuntu/Windows CI;
- adds reusable valid and invalid proof JSON vectors;
- adds an AppKit compilation harness for the ErgoScript contracts;
- adds an audit evidence matrix that maps threats to tests/vectors.

## Scope Boundary

This PR does not claim a complete Bitcoin bridge or Bitcoin finality verifier.
It remains limited to transaction-object facts:

1. supplied non-witness Bitcoin transaction bytes hash to the expected txid;
2. a bounded parser finds an output with the expected script hash.

Bitcoin block inclusion/finality remains a separate layer.

## Testing

```bash
python scripts/check.py
```

The tests cover valid Rosen Bridge bytes, txid byte-order failure, full SegWit
bytes instead of stripped bytes, scriptSig-only matches, truncation, trailing
bytes, unsupported CompactSize, output count bounds, empty scripts, public
vector drift, and AppKit compilation for the canonical and direct verifier
contracts.
