# Checks

Run the complete local verification suite with:

```bash
python scripts/check.py
```

This runs:

1. Python syntax checks for the helper scripts and tests.
2. Python unit tests.
3. Local verification of the public valid proof vector.
4. AppKit compilation of the reusable ErgoScript contracts.

CI uses the same script in two modes:

```bash
python scripts/check.py --python-only
python scripts/check.py --sbt-only
```

Before publishing a branch, a fresh-clone smoke test should run the complete
command above from a clean checkout.
