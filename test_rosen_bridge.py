"""
Test: Verify parser against a real Rosen Bridge Bitcoin → Ergo transaction.

Source: Rosen Bridge Explorer
Event ID: 8d3213214ae1edca33ca7d8a33f897cb38dbb7248f9b6922b17c3d6c3cf1ebc9
Amount: 0.003 BTC ($332.6)
Chain: Bitcoin → Ergo
Date: Sep 06 2025 02:57:35
Status: Successful
"""

from btc_tx_parser import parse_bitcoin_tx, get_script_offsets, get_outputs_section

ROSEN_BRIDGE_TX = (
    '02000000000101f69c854ccbfa5ed35e4c39f5d85fc44763ef9bdeefa045d831f6'
    'd34212a89fb10000000000ffffffff030000000000000000356a33000000000000'
    '0021c400000000000000a82102fd52469f33344592dff455bb2e934d86e1d3f258'
    '7c2eeb635441f5f4cfdc9ef8e09304000000000016001483cf4566652b5385b1f9'
    '4494034f78f177792265f00900000000000016001437f45872b029e6bf139bf43b'
    'e4b44548127a82e3024730440220131b6d94ebc4f3ca649ee6cd92a2f49610db4b'
    '76cbf540a788d52370c713f03602201ac8d6e3f1a6614ef1e38b13fe5e1f7459b4'
    '4f75a3f70799b31ae230cd117f55012102168e8e2cb61100bc4aee81bf3a0544c0'
    'f726c88b6319e45017594e32413f841100000000'
)

EXPECTED_TXID = 'bcb5cb37f1307cc2240a14c7add48b57a479c55ab2123e8bcc02bdf15b3e1ce5'


def test_rosen_bridge():
    tx = parse_bitcoin_tx(ROSEN_BRIDGE_TX)

    # Verify txid
    assert tx['txid'] == EXPECTED_TXID, f"txid mismatch: {tx['txid']}"
    print(f"txid:    {tx['txid']}")
    print(f"match:   True")
    print()

    # Verify structure
    assert tx['version'] == 2
    assert tx['is_segwit'] == True
    assert tx['input_count'] == 1
    assert tx['output_count'] == 3
    print(f"version: {tx['version']}  segwit: {tx['is_segwit']}")
    print(f"inputs:  {tx['input_count']}  outputs: {tx['output_count']}")
    print()

    # Output 0: OP_RETURN with bridge metadata (destination Ergo address)
    out0 = tx['outputs'][0]
    assert out0['value_satoshis'] == 0
    assert out0['script_pubkey_hex'].startswith('6a')  # OP_RETURN
    print(f"Output [0]: OP_RETURN (bridge metadata)")
    print(f"  value:  {out0['value_btc']:.8f} BTC")
    print(f"  script: {out0['script_pubkey_hex'][:60]}...")
    print()

    # Output 1: 0.003 BTC deposit to Rosen multisig
    out1 = tx['outputs'][1]
    assert out1['value_satoshis'] == 300000  # 0.003 BTC
    print(f"Output [1]: Bridge deposit (to Rosen multisig)")
    print(f"  value:  {out1['value_btc']:.8f} BTC")
    print(f"  script: {out1['script_pubkey_hex']}")
    print(f"  hash:   {out1['script_hash_sha256']}")
    print()

    # Output 2: change
    out2 = tx['outputs'][2]
    print(f"Output [2]: Change")
    print(f"  value:  {out2['value_btc']:.8f} BTC")
    print()

    # ErgoScript context preparation
    # These are the exact values needed to spend the contract
    offsets = get_script_offsets(tx['stripped_tx_hex'])
    stripped_bytes = bytes.fromhex(tx['stripped_tx_hex'])

    print(f"=== ErgoScript Context (what you'd pass to the contract) ===")
    print(f"  R4 (txid natural):     {tx['txid_natural']}")
    print(f"  R5 (script hash out1): {out1['script_hash_sha256']}")
    print(f"  var(1) stripped size:   {len(tx['stripped_tx_hex'])//2} bytes")
    print(f"  var(1) stripped hex:    {tx['stripped_tx_hex'][:60]}...")
    assert tx['is_segwit'] and len(tx['stripped_tx_hex']) < len(ROSEN_BRIDGE_TX)
    print(f"  SegWit stripped:        {len(ROSEN_BRIDGE_TX)//2} -> {len(tx['stripped_tx_hex'])//2} bytes")
    print()

    print(f"=== Byte Offsets for Each Output (ErgoScript var(2) and var(3)) ===")
    for i, off in enumerate(offsets):
        script_slice = stripped_bytes[off['offset']:off['offset'] + off['length']]
        print(f"  Output [{i}]: var(2)={off['offset']}  var(3)={off['length']}")
        print(f"    script at offset: {script_slice.hex()[:50]}...")
        # Verify round-trip: sliced script matches parsed script
        assert script_slice.hex() == tx['outputs'][i]['script_pubkey_hex']
    print(f"  All offsets verified against parsed output scripts")
    print()

    # Complete worked example for Output 1 (the bridge deposit)
    o1 = offsets[1]
    print(f"=== Complete Worked Example: Verify Output 1 (Bridge Deposit) ===")
    print(f"  To spend the contract box, pass these context vars:")
    print(f"    var(1) = stripped tx bytes ({len(tx['stripped_tx_hex'])//2} bytes)")
    print(f"    var(2) = {o1['offset']}  (scriptPubKey byte offset)")
    print(f"    var(3) = {o1['length']}  (scriptPubKey byte length)")
    print(f"  Contract will verify:")
    print(f"    SHA256(SHA256(var(1))) == R4  ->  {tx['txid_natural']}")
    print(f"    SHA256(var(1)[{o1['offset']}:{o1['offset']+o1['length']}]) == R5  ->  {out1['script_hash_sha256']}")
    print()

    # === Hardened contract: outputs section commitment (R6) ===
    out_section = get_outputs_section(tx['stripped_tx_hex'])
    outputs_bytes = bytes.fromhex(out_section['outputs_hex'])

    print(f"=== Outputs Section Commitment (hardened contract) ===")
    print(f"  R6 (outputs hash):     {out_section['outputs_hash']}")
    print(f"  outputs section size:  {out_section['outputs_size']} bytes")
    print(f"  starts at byte:        {out_section['outputs_start']} in stripped tx")
    print()

    print(f"=== Relative Offsets Within Outputs Section ===")
    for i, ro in enumerate(out_section['relative_offsets']):
        script_slice = outputs_bytes[ro['offset']:ro['offset'] + ro['length']]
        print(f"  Output [{i}]: rel_offset={ro['offset']}  len={ro['length']}")
        print(f"    script: {script_slice.hex()[:50]}...")
        assert script_slice.hex() == tx['outputs'][i]['script_pubkey_hex']
    print(f"  All relative offsets verified")
    print()

    # Complete worked example for hardened contract
    ro1 = out_section['relative_offsets'][1]
    print(f"=== Hardened Contract: Verify Output 1 (Bridge Deposit) ===")
    print(f"  Box registers:")
    print(f"    R4 = {tx['txid_natural']}")
    print(f"    R5 = {out1['script_hash_sha256']}")
    print(f"    R6 = {out_section['outputs_hash']}")
    print(f"  Context vars:")
    print(f"    var(1) = stripped tx bytes ({len(tx['stripped_tx_hex'])//2} bytes)")
    print(f"    var(2) = {ro1['offset']}  (relative offset within outputs section)")
    print(f"    var(3) = {ro1['length']}  (scriptPubKey length)")
    print(f"    var(4) = outputs section bytes ({out_section['outputs_size']} bytes)")
    print(f"  Contract verifies:")
    print(f"    SHA256(SHA256(var(1))) == R4")
    print(f"    SHA256(var(4)) == R6")
    print(f"    SHA256(var(4)[{ro1['offset']}:{ro1['offset']+ro1['length']}]) == R5")
    print()

    print("All assertions passed")


if __name__ == '__main__':
    print("=== Rosen Bridge Bitcoin Transaction Test ===")
    print()
    test_rosen_bridge()
