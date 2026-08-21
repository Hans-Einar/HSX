"""Public frozen interface for the side-by-side HSX debugger foundation."""

from .contracts import *
from .contracts import __all__
from .contracts import EvidenceGrade as _EvidenceGrade

from .addresses import *
from .addresses import __all__ as _addresses_all
from .identity import *
from .identity import __all__ as _identity_all
from .metadata import *
from .metadata import __all__ as _metadata_all
from .results import *
from .results import __all__ as _results_all
from .results import _register_contract_enums as _register_result_contract_enums

# InspectionContext embeds the RF-002 GenerationStamp. Register its closed EvidenceGrade
# enum deterministically at package import so generic RF-004 result deep-freezing never
# depends on test/import order.
_register_result_contract_enums(_EvidenceGrade)

from .recipes import *
from .recipes import __all__ as _recipes_all
from .snapshot import *
from .snapshot import __all__ as _snapshot_all
from .artifacts import *
from .artifacts import __all__ as _artifacts_all
from .legacy_symbols import *
from .legacy_symbols import __all__ as _legacy_symbols_all
from .sources import *
from .sources import __all__ as _sources_all
from .stack import *
from .stack import __all__ as _stack_all
from .handles import *
from .handles import __all__ as _handles_all
from .inspection import *
from .inspection import __all__ as _inspection_all

__all__ = [
    *__all__,
    *_identity_all,
    *_addresses_all,
    *_results_all,
    *_metadata_all,
    *_recipes_all,
    *_snapshot_all,
    *_artifacts_all,
    *_legacy_symbols_all,
    *_sources_all,
    *_stack_all,
    *_handles_all,
    *_inspection_all,
]
