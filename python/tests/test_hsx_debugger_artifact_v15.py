from __future__ import annotations

import pytest

from hsx_debugger import ResolutionStatus
from test_hsx_debugger_artifacts import build, portable_fixture


def test_real_portable_index_resolves_exact_symbol_id_without_name_aliasing() -> None:
    f = portable_fixture()
    result = build(f)
    assert result.status is ResolutionStatus.RESOLVED
    index = result.values[0]

    local = index.symbol_by_id("local")
    global_ = index.symbol_by_id("global")
    missing = index.symbol_by_id("missing")

    assert local.status is ResolutionStatus.RESOLVED
    assert len(local.values) == 1
    assert local.values[0].symbol_id == "local"
    assert local.values[0].name == "value"

    assert global_.status is ResolutionStatus.RESOLVED
    assert len(global_.values) == 1
    assert global_.values[0].symbol_id == "global"
    assert global_.values[0].name == "value"

    # Equal display names remain independent exact identities; no name-based alias is used.
    assert local.values[0] != global_.values[0]
    assert missing.status is ResolutionStatus.UNAVAILABLE
    assert missing.values == ()
    assert missing.diagnostics[0].code == "symbol_id_unavailable"


def test_symbol_by_id_rejects_non_exact_empty_input() -> None:
    index = build(portable_fixture()).values[0]
    with pytest.raises(ValueError, match="symbol_id must be a non-empty string"):
        index.symbol_by_id("")
