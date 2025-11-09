from python import asm as hsx_asm


def test_adc_encoding_parsing():
    expected_word = ((hsx_asm.OPC["ADC"] & 0xFF) << 24) | (2 << 20) | (3 << 16) | (4 << 12)
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        [
            ".text\n",
            "adc_test:\n",
            "    ADC R2, R3, R4\n",
        ],
        for_object=True,
    )
    assert code[0] == expected_word


def test_sbc_encoding_parsing():
    expected_word = ((hsx_asm.OPC["SBC"] & 0xFF) << 24) | (5 << 20) | (6 << 16) | (7 << 12)
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        [
            ".text\n",
            "sbc_test:\n",
            "    SBC R5, R6, R7\n",
        ],
        for_object=True,
    )
    assert code[0] == expected_word
