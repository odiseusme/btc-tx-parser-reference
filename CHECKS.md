# Checks

Run the complete local verification suite with:

```bash
python scripts/check.py
```

This runs:

1. Python syntax checks for the helper scripts and tests.
2. Python unit tests.
3. Local verification of the public valid proof vector.
4. AppKit compilation of the reusable ErgoScript contracts. The contracts are
   now also EXECUTED against every public test vector: each
   `test-vectors/*.proof.json` is reduced against its declared contract in a
   real `ErgoLikeContext` (registers R4/R5/R6 plus context variable 1), and the
   harness asserts that vectors under `valid/` accept and vectors under
   `invalid/` reject (reduction to false or a thrown evaluation exception). A
   mutation canary flips a byte of R5 on a known-good vector to prove the
   harness is not vacuously green.

CI uses the same script in two modes:

```bash
python scripts/check.py --python-only
python scripts/check.py --sbt-only
```

Before publishing a branch, a fresh-clone smoke test should run the complete
command above from a clean checkout.
