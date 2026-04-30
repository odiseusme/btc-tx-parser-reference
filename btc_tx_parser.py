"""
Bitcoin Raw Transaction Parser — Reference Implementation
=========================================================

Context: ergoplatform/sigmastate-interpreter#1114
Kushti's bounty asks for ErgoScript that parses a Bitcoin transaction,
verifies its txid (R4), and checks an output script hash (R5).

This Python script demonstrates the exact parsing logic needed.
It serves as a readable reference for anyone implementing it in ErgoScript.

Bitcoin transaction format (legacy):
  [version:4] [input_count:varint] [inputs...] [output_count:varint] [outputs...] [locktime:4]

Each input:
  [prev_txid:32] [prev_vout:4] [script_len:varint] [script_sig:var] [sequence:4]

Each output:
  [value:8] [script_len:varint] [script_pubkey:var]

txid = reverse(SHA256(SHA256(raw_bytes)))

For SegWit transactions, the raw format includes a marker (0x00) and flag (0x01)
after the version, plus witness data before locktime. The txid is computed
from the serialization WITHOUT marker/flag/witness.

Author: Nir (odiseusme) — Rosen Bridge watcher operator
"""

import hashlib
import struct


def read_varint(data: bytes, offset: int) -> tuple[int, int]:
    """
    Read a Bitcoin variable-length integer.

    Encoding:
      < 0xFD       → 1 byte (the value itself)
      0xFD + 2 bytes → uint16 LE
      0xFE + 4 bytes → uint32 LE
      0xFF + 8 bytes → uint64 LE

    Returns (value, new_offset).
    """
    first = data[offset]
    if first < 0xFD:
        return first, offset + 1
    elif first == 0xFD:
        return struct.unpack_from('<H', data, offset + 1)[0], offset + 3
    elif first == 0xFE:
        return struct.unpack_from('<I', data, offset + 1)[0], offset + 5
    else:
        return struct.unpack_from('<Q', data, offset + 1)[0], offset + 9


def encode_varint(n: int) -> bytes:
    """Encode an integer as a Bitcoin varint."""
    if n < 0xFD:
        return bytes([n])
    elif n <= 0xFFFF:
        return b'\xfd' + struct.pack('<H', n)
    elif n <= 0xFFFFFFFF:
        return b'\xfe' + struct.pack('<I', n)
    else:
        return b'\xff' + struct.pack('<Q', n)


def double_sha256(data: bytes) -> bytes:
    """Bitcoin's standard double-SHA256 hash."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def display_to_natural(display_txid: str) -> str:
    """
    Convert a Bitcoin explorer-format txid (display order) to the natural
    double-SHA256 byte order required by ErgoScript register R4.

    Bitcoin explorers and most libraries display the txid as
    reverse(SHA256(SHA256(tx_bytes))). R4 expects the UN-reversed natural
    form, because ErgoScript has no .reverse on Coll[Byte].

    Input:  64-character hex string (32 bytes). Leading "0x" tolerated.
    Output: 64-character hex string in natural double-SHA256 order.
    Raises: ValueError if input is not 64 hex characters.
    """
    cleaned = display_txid.strip().lower()
    if cleaned.startswith('0x'):
        cleaned = cleaned[2:]
    if len(cleaned) != 64 or any(c not in '0123456789abcdef' for c in cleaned):
        raise ValueError(
            f'Expected 64 hex chars (32 bytes), got {len(cleaned)}: {display_txid!r}'
        )
    return bytes.fromhex(cleaned)[::-1].hex()


def natural_to_display(natural_txid: str) -> str:
    """Inverse of display_to_natural. Same byte-reverse operation."""
    return display_to_natural(natural_txid)


def get_script_offsets(stripped_hex: str) -> list:
    """
    Compute byte offsets of each output's scriptPubKey within stripped tx bytes.
    Returns list of dicts with 'offset' and 'length' for each output.
    These are the exact values for the baseline ErgoScript context vars 2 and 3.
    """
    data = bytes.fromhex(stripped_hex)
    offset = 4  # skip version

    # Skip inputs
    input_count, offset = read_varint(data, offset)
    for _ in range(input_count):
        offset += 32  # prev txid
        offset += 4   # prev vout
        script_len, offset = read_varint(data, offset)
        offset += script_len  # script_sig
        offset += 4   # sequence

    # Parse outputs, recording script offsets
    output_count, offset = read_varint(data, offset)
    results = []
    for _ in range(output_count):
        offset += 8  # value
        script_len, offset = read_varint(data, offset)
        results.append({'offset': offset, 'length': script_len})
        offset += script_len

    return results


def get_outputs_section(stripped_hex: str) -> dict:
    """
    Extract the outputs section from stripped Bitcoin transaction bytes.

    The outputs section = [output_count varint] + [all outputs].
    This is everything between the last input and the locktime.

    Returns dict with:
      outputs_hex:       hex string of the outputs section bytes
      outputs_hash:      SHA256 hash of outputs section (for ErgoScript R6)
      outputs_start:     byte offset where outputs section starts in stripped tx
      relative_offsets:  list of dicts with 'offset' and 'length' for each
                         output's scriptPubKey RELATIVE to outputs section start
    """
    data = bytes.fromhex(stripped_hex)
    offset = 4  # skip version

    # Skip inputs
    input_count, offset = read_varint(data, offset)
    for _ in range(input_count):
        offset += 32  # prev txid
        offset += 4   # prev vout
        script_len, offset = read_varint(data, offset)
        offset += script_len  # script_sig
        offset += 4   # sequence

    # Mark start of outputs section (includes output_count varint)
    outputs_section_start = offset

    # Parse through outputs to find end
    output_count, offset = read_varint(data, offset)
    relative_offsets = []
    for _ in range(output_count):
        offset += 8  # value
        script_len, offset = read_varint(data, offset)
        # Offset relative to outputs section start
        rel_offset = offset - outputs_section_start
        relative_offsets.append({'offset': rel_offset, 'length': script_len})
        offset += script_len

    # outputs section = from outputs_section_start to just before locktime
    outputs_section_end = offset
    outputs_bytes = data[outputs_section_start:outputs_section_end]
    outputs_hash = hashlib.sha256(outputs_bytes).hexdigest()

    return {
        'outputs_hex': outputs_bytes.hex(),
        'outputs_hash': outputs_hash,
        'outputs_start': outputs_section_start,
        'outputs_size': len(outputs_bytes),
        'relative_offsets': relative_offsets,
    }


def parse_bitcoin_tx(raw_hex: str) -> dict:
    """
    Parse a raw Bitcoin transaction from hex string.

    Returns dict with:
      txid, version, is_segwit, inputs, outputs, locktime

    Each output includes:
      value_satoshis, value_btc, script_pubkey_hex, script_hash_sha256

    The script_hash_sha256 is what Kushti's bounty needs matched against R5.
    The txid is what needs matched against R4.
    """
    raw = bytes.fromhex(raw_hex)
    offset = 0

    # Version (4 bytes, little-endian)
    version = struct.unpack_from('<I', raw, offset)[0]
    offset += 4

    # SegWit detection: marker=0x00 flag=0x01 after version
    is_segwit = False
    if raw[offset] == 0x00 and raw[offset + 1] == 0x01:
        is_segwit = True
        offset += 2

    # --- Parse Inputs ---
    input_count, offset = read_varint(raw, offset)
    inputs = []
    for _ in range(input_count):
        prev_txid = raw[offset:offset + 32][::-1].hex()
        offset += 32
        prev_vout = struct.unpack_from('<I', raw, offset)[0]
        offset += 4
        script_len, offset = read_varint(raw, offset)
        script_sig = raw[offset:offset + script_len].hex()
        offset += script_len
        sequence = struct.unpack_from('<I', raw, offset)[0]
        offset += 4
        inputs.append({
            'prev_txid': prev_txid,
            'prev_vout': prev_vout,
            'script_sig': script_sig,
            'sequence': sequence,
        })

    # --- Parse Outputs ---
    output_count, offset = read_varint(raw, offset)
    outputs = []
    for _ in range(output_count):
        value = struct.unpack_from('<Q', raw, offset)[0]
        offset += 8
        script_len, offset = read_varint(raw, offset)
        script_pubkey = raw[offset:offset + script_len]
        offset += script_len
        outputs.append({
            'value_satoshis': value,
            'value_btc': value / 100_000_000,
            'script_pubkey_hex': script_pubkey.hex(),
            'script_hash_sha256': hashlib.sha256(script_pubkey).hexdigest(),
        })

    # --- Witness (SegWit only, skip for txid) ---
    if is_segwit:
        for _ in range(input_count):
            item_count, offset = read_varint(raw, offset)
            for _ in range(item_count):
                item_len, offset = read_varint(raw, offset)
                offset += item_len

    # Locktime (4 bytes, little-endian)
    locktime = struct.unpack_from('<I', raw, offset)[0]
    offset += 4

    # --- Build stripped serialization (without SegWit marker/flag/witness) ---
    # This is what goes into ErgoScript context var(1).
    # For legacy transactions, stripped == raw. For SegWit, witness is removed.
    if is_segwit:
        stripped = struct.pack('<I', version)
        stripped += encode_varint(input_count)
        for inp in inputs:
            stripped += bytes.fromhex(inp['prev_txid'])[::-1]
            stripped += struct.pack('<I', inp['prev_vout'])
            sig = bytes.fromhex(inp['script_sig'])
            stripped += encode_varint(len(sig)) + sig
            stripped += struct.pack('<I', inp['sequence'])
        stripped += encode_varint(output_count)
        for out in outputs:
            stripped += struct.pack('<Q', out['value_satoshis'])
            spk = bytes.fromhex(out['script_pubkey_hex'])
            stripped += encode_varint(len(spk)) + spk
        stripped += struct.pack('<I', locktime)
    else:
        stripped = raw

    # --- Compute txid ---
    txid_natural = double_sha256(stripped).hex()        # natural order → R4
    txid = double_sha256(stripped)[::-1].hex()          # reversed → Bitcoin display

    return {
        'txid': txid,
        'txid_natural': txid_natural,
        'stripped_tx_hex': stripped.hex(),
        'version': version,
        'is_segwit': is_segwit,
        'input_count': input_count,
        'inputs': inputs,
        'output_count': output_count,
        'outputs': outputs,
        'locktime': locktime,
        'size_bytes': len(raw),
    }


def check_against_ergo_registers(tx: dict, r4_txid_natural: str, r5_script_hash: str) -> dict:
    """
    Simulate what the ErgoScript contract needs to verify:
      - R4 contains the expected Bitcoin txid in NATURAL hash order
      - R5 contains the SHA-256 hash of an output's scriptPubKey

    Returns dict with match results.
    """
    txid_match = tx['txid_natural'] == r4_txid_natural

    matching_outputs = []
    for i, out in enumerate(tx['outputs']):
        if out['script_hash_sha256'] == r5_script_hash:
            matching_outputs.append(i)

    return {
        'txid_matches_r4': txid_match,
        'outputs_matching_r5': matching_outputs,
        'would_pass': txid_match and len(matching_outputs) > 0,
    }


# ═══════════════════════════════════════════════════════════
# Test with the first-ever Bitcoin transaction
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    # Satoshi → Hal Finney, Jan 12 2009
    SATOSHI_TX = (
        '0100000001c997a5e56e104102fa209c6a852dd90660a20b2d9c352423edce2585'
        '7fcd3704000000004847304402204e45e16932b8af514961a1d3a1a25fdf3f4f77'
        '32e9d624c6c61548ab5fb8cd410220181522ec8eca07de4860a4acdd12909d831c'
        'c56cbbac4622082221a8768d1d0901ffffffff0200ca9a3b000000004341'
        '04ae1a62fe09c5f51b13905f07f06b99a2f7159b2225f374cd378d71302fa28414'
        'e7aab37397f554a7df5f142c21c1b7303b8a0626f1baded5c72a704f7e6cd84cac'
        '00286bee0000000043410411db93e1dcdb8a016b49840f8c53bc1eb68a382e97b1'
        '482ecad7b148a6909a5cb2e0eaddfb84ccf9744464f82e160bfa9b8b64f9d4c03f'
        '999b8643f656b412a3ac00000000'
    )

    KNOWN_TXID = 'f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16'

    tx = parse_bitcoin_tx(SATOSHI_TX)

    print('Bitcoin Transaction Parser — Reference for ErgoScript')
    print('=' * 55)
    print(f'txid:          {tx["txid"]}')
    print(f'txid_natural:  {tx["txid_natural"]}')
    print(f'               (this is what goes into ErgoScript R4)')
    print(f'version:       {tx["version"]}')
    print(f'segwit:        {tx["is_segwit"]}')
    print(f'inputs:        {tx["input_count"]}')
    print(f'outputs:       {tx["output_count"]}')
    print(f'locktime:      {tx["locktime"]}')
    print(f'size:          {tx["size_bytes"]} bytes')
    print(f'stripped size: {len(tx["stripped_tx_hex"])//2} bytes')
    print(f'               (this is what goes into ErgoScript context var 1)')
    print()

    for i, out in enumerate(tx['outputs']):
        print(f'Output [{i}]:')
        print(f'  value:       {out["value_btc"]:.8f} BTC')
        print(f'  script:      {out["script_pubkey_hex"][:50]}...')
        print(f'  script_hash: {out["script_hash_sha256"]}')
        print()

    # Verify txid
    assert tx['txid'] == KNOWN_TXID, 'txid mismatch!'
    print('✅ txid matches known value')
    print()

    # Simulate ErgoScript register check (using natural hash order for R4)
    target_script_hash = tx['outputs'][0]['script_hash_sha256']
    result = check_against_ergo_registers(tx, tx['txid_natural'], target_script_hash)
    print('Simulated ErgoScript register check:')
    print(f'  R4 (txid natural):   {result["txid_matches_r4"]}')
    print(f'  R5 (script hash):    output(s) {result["outputs_matching_r5"]}')
    print(f'  Contract would pass: {result["would_pass"]}')
