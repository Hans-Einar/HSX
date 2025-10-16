import importlib.util
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def test_global_string_lowering_emits_data_section():
    ll = """@msg = internal constant [3 x i8] c\"OK\\00\", align 1\n\n"""
    ll += """define dso_local i32 @main(i32 %idx) {\nentry:\n  %idx64 = sext i32 %idx to i64\n  %ptr = getelementptr inbounds [3 x i8], ptr @msg, i64 0, i64 %idx64\n  %byte = load i8, ptr %ptr, align 1\n  %res = sext i8 %byte to i32\n  ret i32 %res\n}\n"""
    asm = HSX_LLC.compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line]
    assert '.data' in lines
    assert 'msg:' in lines
    byte_lines = [line for line in lines if line.strip().startswith('.byte')]
    assert any('0x4F' in line for line in byte_lines)
    assert '.text' in lines
    assert any(line.startswith('LDI32') and 'msg' in line for line in lines)
    assert any(line.startswith('LDB ') for line in lines)


def test_global_int_lowering_loads_with_ld():
    ll = """@idx = dso_local global i32 0, align 4\n\n"""
    ll += """define dso_local i32 @main() {\nentry:\n  %val = load volatile i32, ptr @idx, align 4\n  ret i32 %val\n}\n"""
    asm = HSX_LLC.compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line]
    assert '.data' in lines and 'idx:' in lines
    assert any(line.strip().startswith('.word') for line in lines)
    assert '.text' in lines
    assert any(line.startswith('LDI32') and 'idx' in line for line in lines)
    assert any(line.startswith('LD ') for line in lines)


def test_quoted_globals_do_not_collide_with_existing_names():
    ll = (
        '@__hsx_quoted_global_1 = dso_local global i32 7, align 4\n'
        '@"??_C@_03@AB@HI@\\00" = private unnamed_addr constant [3 x i8] c"HI\\00", align 1\n\n'
        'define dso_local i32 @main() {\n'
        'entry:\n'
        '  %ptr = getelementptr inbounds [3 x i8], ptr @"??_C@_03@AB@HI@\\00", i32 0, i32 0\n'
        '  %val = load i8, ptr %ptr, align 1\n'
        '  %ext = sext i8 %val to i32\n'
        '  ret i32 %ext\n'
        '}\n'
    )
    asm = HSX_LLC.compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line]
    labels = [line[:-1] for line in lines if line.endswith(':') and not line.startswith(' ')]
    assert '__hsx_quoted_global_1' in labels
    quoted_labels = [name for name in labels if name.startswith('__hsx_quoted_global_')]
    assert len(quoted_labels) >= 2
    assert len(set(quoted_labels)) == len(quoted_labels)
    new_labels = [name for name in quoted_labels if name != '__hsx_quoted_global_1']
    assert new_labels
    assert any(line.startswith('LDI32') and new_labels[0] in line for line in lines)


def test_quoted_globals_with_section_attributes_are_parsed():
    ll = (
        '@"??_C@_0CP@IBHPODGP@mailbox?5producer?3?5failed?5to?5open@" = '
        'linkonce_odr dso_local unnamed_addr constant [36 x i8] '
        'c"mailbox producer: failed to open\\0A\\00", section ".rdata", align 2\n\n'
        'define dso_local i32 @main() {\n'
        'entry:\n'
        '  %ptr = getelementptr inbounds [36 x i8], '
        'ptr @"??_C@_0CP@IBHPODGP@mailbox?5producer?3?5failed?5to?5open@", i64 0, i64 0\n'
        '  %val = load i8, ptr %ptr, align 1\n'
        '  %ext = sext i8 %val to i32\n'
        '  ret i32 %ext\n'
        '}\n'
    )
    asm = HSX_LLC.compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line]
    labels = [line[:-1] for line in lines if line.endswith(':') and not line.startswith(' ')]
    quoted_labels = [name for name in labels if name.startswith('__hsx_quoted_global_')]
    assert quoted_labels, 'expected sanitized quoted global label in data section'
    assert any(line.strip().startswith('.byte') for line in lines), 'expected emitted byte data for string'
    assert any(label in line for label in quoted_labels for line in lines if line.startswith('LDI32'))


def test_comdat_alias_lines_are_ignored_during_sanitization():
    ll = (
        '$"??_C@_0M@ABCD@foo?$AA@" = comdat any\n'
        '@"??_C@_0M@ABCD@foo?$AA@" = linkonce_odr dso_local unnamed_addr constant [4 x i8] '
        'c"foo\\00", comdat, align 1\n\n'
        'define dso_local i32 @main() {\n'
        'entry:\n'
        '  %ptr = getelementptr inbounds [4 x i8], '
        'ptr @"??_C@_0M@ABCD@foo?$AA@", i32 0, i32 0\n'
        '  %val = load i8, ptr %ptr, align 1\n'
        '  %ext = sext i8 %val to i32\n'
        '  ret i32 %ext\n'
        '}\n'
    )
    asm = HSX_LLC.compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line]
    labels = [line[:-1] for line in lines if line.endswith(':') and not line.startswith(' ')]
    quoted_labels = [name for name in labels if name.startswith('__hsx_quoted_global_')]
    assert quoted_labels, 'expected sanitized quoted global label in data section'
    comdat_lines = [line for line in lines if line.startswith('$"')]
    assert not comdat_lines, 'COMDAT alias lines should not appear in the sanitized output'
    assert any(label in line for label in quoted_labels for line in lines if line.startswith('LDI32'))
