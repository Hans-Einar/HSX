"""Epoch-bound, frontend-neutral inspection composition for RF-004.

The service composes immutable artifact metadata, snapshot reads, StackService, and
LocationEvaluator. It owns epoch/session lifetime and domain handles only; run control,
transport, frontend presentation, persistent watches, and runtime adapters remain outside.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import TypeAlias

from .addresses import AddressStatus, ArchitectureDescriptor, HsxAddress, Permission
from .artifacts import DebugArtifactIndex
from .handles import (
    DomainHandle,
    EpochHandleStore,
    HandleKind,
    HandleResolution,
    InvalidationResult,
    ScopeKind,
)
from .identity import AbiDescriptorRef, DebugBindingValidator, InspectionContext, StopEpochId
from .metadata import SymbolKind, SymbolRecord
from .recipes import LocationEvaluator, RecipeLimits, RecipeRequestLimits, UnwindFrame
from .results import (
    ConstantExpression,
    Diagnostic,
    DisassembledInstruction,
    DisassemblyBlock,
    EvaluatedValue,
    ExpressionKind,
    ExpressionValue,
    InspectionOpenStatus,
    InspectionResult,
    InspectionStatus,
    InstructionBytes,
    InvalidationStatus,
    MemoryBlock,
    MemoryExpression,
    PageRequest,
    RegisterExpression,
    RegisterSelection,
    RegisterSet,
    ResolutionStatus,
    ScalarBytes,
    ServiceCloseStatus,
    SnapshotExpression,
    SymbolExpression,
    ValueAvailability,
    VariableExpression,
)
from .snapshot import SnapshotReadPort, fence_snapshot_result, require_snapshot_read_set
from .stack import StackService


_ACCEPTED_PROFILE = "hsx.portable-debug-runtime/1"


def _diag(code: str, message: str, *, component: str = "inspection") -> Diagnostic:
    return Diagnostic(code, message, component=component)


def _diagnostics(value) -> tuple[Diagnostic, ...]:
    items = tuple(value)
    if not all(isinstance(item, Diagnostic) for item in items):
        raise TypeError("diagnostics must contain Diagnostic values")
    return items


@dataclass(frozen=True, slots=True)
class InspectionServiceCreateResult:
    """Dedicated 1.4 lifecycle/control factory envelope."""

    status: ResolutionStatus
    service: InspectionService | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not ResolutionStatus:
            raise TypeError("status must be ResolutionStatus")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is ResolutionStatus.RESOLVED:
            if self.service is None or diagnostics:
                raise ValueError("RESOLVED requires one service and no diagnostics")
        elif self.service is not None or not diagnostics:
            raise ValueError("failed creation requires no service and diagnostics")


@dataclass(frozen=True, slots=True)
class InspectionOpenResult:
    """Dedicated lifecycle envelope; session is an opaque control reference."""

    status: InspectionOpenStatus
    session: EpochInspectionSession | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not InspectionOpenStatus:
            raise TypeError("status must be InspectionOpenStatus")
        diagnostics = _diagnostics(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.status is InspectionOpenStatus.OPENED:
            if self.session is None or diagnostics:
                raise ValueError("OPENED requires one session and no diagnostics")
        elif self.session is not None or not diagnostics:
            raise ValueError("failed open requires no session and diagnostics")


@dataclass(frozen=True, slots=True)
class ServiceCloseResult:
    status: ServiceCloseStatus
    invalidation: InvalidationResult | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not ServiceCloseStatus:
            raise TypeError("status must be ServiceCloseStatus")
        if self.invalidation is not None and not isinstance(self.invalidation, InvalidationResult):
            raise TypeError("invalidation must be InvalidationResult or None")
        object.__setattr__(self, "diagnostics", _diagnostics(self.diagnostics))


@dataclass(frozen=True, slots=True)
class FrameRecord:
    context: InspectionContext
    handle: DomainHandle
    unwind: UnwindFrame

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.FRAME:
            raise TypeError("handle must be a FRAME DomainHandle")
        if not isinstance(self.unwind, UnwindFrame):
            raise TypeError("unwind must be UnwindFrame")
        if self.handle.context != self.context or self.unwind.context != self.context:
            raise ValueError("frame record evidence must share one exact context")


@dataclass(frozen=True, slots=True)
class FramePage:
    total_frames: int
    offset: int
    frames: tuple[FrameRecord, ...]

    def __post_init__(self) -> None:
        if isinstance(self.total_frames, bool) or not isinstance(self.total_frames, int) or self.total_frames < 0:
            raise ValueError("total_frames must be an integer >= 0")
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError("offset must be an integer >= 0")
        frames = tuple(self.frames)
        if not all(isinstance(item, FrameRecord) for item in frames):
            raise TypeError("frames must contain FrameRecord values")
        object.__setattr__(self, "frames", frames)


@dataclass(frozen=True, slots=True)
class ScopeRecord:
    context: InspectionContext
    handle: DomainHandle
    frame_handle: DomainHandle
    kind: ScopeKind
    name: str
    expensive: bool

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.SCOPE:
            raise TypeError("handle must be a SCOPE DomainHandle")
        if not isinstance(self.frame_handle, DomainHandle) or self.frame_handle.kind is not HandleKind.FRAME:
            raise TypeError("frame_handle must be a FRAME DomainHandle")
        if type(self.kind) is not ScopeKind:
            raise TypeError("kind must be ScopeKind")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be non-empty")
        if not isinstance(self.expensive, bool):
            raise TypeError("expensive must be bool")
        if self.handle.context != self.context or self.frame_handle.context != self.context:
            raise ValueError("scope handles must share the record context")


@dataclass(frozen=True, slots=True)
class ScopeSet:
    frame_handle: DomainHandle
    scopes: tuple[ScopeRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.frame_handle, DomainHandle) or self.frame_handle.kind is not HandleKind.FRAME:
            raise TypeError("frame_handle must be a FRAME DomainHandle")
        scopes = tuple(self.scopes)
        if not all(isinstance(item, ScopeRecord) for item in scopes):
            raise TypeError("scopes must contain ScopeRecord values")
        if any(item.frame_handle != self.frame_handle for item in scopes):
            raise ValueError("scope set must reference one frame handle")
        object.__setattr__(self, "scopes", scopes)


@dataclass(frozen=True, slots=True)
class SymbolVariableRecord:
    context: InspectionContext
    handle: DomainHandle
    scope_handle: DomainHandle
    symbol_id: str
    declaration_order: int
    evaluated: EvaluatedValue

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.VARIABLE:
            raise TypeError("handle must be a VARIABLE DomainHandle")
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        if not isinstance(self.symbol_id, str) or not self.symbol_id:
            raise ValueError("symbol_id must be non-empty")
        if isinstance(self.declaration_order, bool) or not isinstance(self.declaration_order, int) or self.declaration_order < 0:
            raise ValueError("declaration_order must be an integer >= 0")
        if not isinstance(self.evaluated, EvaluatedValue):
            raise TypeError("evaluated must be EvaluatedValue")
        if self.evaluated.symbol_id != self.symbol_id:
            raise ValueError("evaluated symbol_id must equal record symbol_id")
        if self.handle.context != self.context or self.scope_handle.context != self.context:
            raise ValueError("variable handles must share one context")


@dataclass(frozen=True, slots=True)
class RegisterVariableRecord:
    context: InspectionContext
    handle: DomainHandle
    scope_handle: DomainHandle
    register_id: str
    register_order: int
    evaluated: ExpressionValue

    def __post_init__(self) -> None:
        if not isinstance(self.context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(self.handle, DomainHandle) or self.handle.kind is not HandleKind.VARIABLE:
            raise TypeError("handle must be a VARIABLE DomainHandle")
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        if not isinstance(self.register_id, str) or not self.register_id:
            raise ValueError("register_id must be non-empty")
        if isinstance(self.register_order, bool) or not isinstance(self.register_order, int) or self.register_order < 0:
            raise ValueError("register_order must be an integer >= 0")
        if not isinstance(self.evaluated, ExpressionValue):
            raise TypeError("evaluated must be ExpressionValue")
        if self.evaluated.expression_kind is not ExpressionKind.REGISTER or self.evaluated.source_id != self.register_id:
            raise ValueError("evaluated register identity differs")
        if self.handle.context != self.context or self.scope_handle.context != self.context:
            raise ValueError("variable handles must share one context")


ScopeValueRecord: TypeAlias = SymbolVariableRecord | RegisterVariableRecord


@dataclass(frozen=True, slots=True)
class VariablePage:
    scope_handle: DomainHandle
    total_variables: int
    offset: int
    variables: tuple[ScopeValueRecord, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scope_handle, DomainHandle) or self.scope_handle.kind is not HandleKind.SCOPE:
            raise TypeError("scope_handle must be a SCOPE DomainHandle")
        if isinstance(self.total_variables, bool) or not isinstance(self.total_variables, int) or self.total_variables < 0:
            raise ValueError("total_variables must be an integer >= 0")
        if isinstance(self.offset, bool) or not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError("offset must be an integer >= 0")
        variables = tuple(self.variables)
        if not all(isinstance(item, (SymbolVariableRecord, RegisterVariableRecord)) for item in variables):
            raise TypeError("variables must contain ScopeValueRecord values")
        if any(item.scope_handle != self.scope_handle for item in variables):
            raise ValueError("variable page must retain one exact scope handle")
        object.__setattr__(self, "variables", variables)


def _failed_create(status: ResolutionStatus, code: str, message: str) -> InspectionServiceCreateResult:
    return InspectionServiceCreateResult(status, None, (_diag(code, message),))


def _failure(context: InspectionContext, status: InspectionStatus, code: str, message: str):
    return InspectionResult(status, context, None, (_diag(code, message),))


def _page_bounds(total: int, page: PageRequest) -> tuple[int, int]:
    start = min(page.offset, total)
    return start, min(start + page.limit, total)


class InspectionService:
    def __init__(self, index, read_port, architecture, abi, profile_limits, stack_service, location_evaluator) -> None:
        self._index = index
        self._read_port = read_port
        self._architecture = architecture
        self._abi = abi
        self._profile_limits = profile_limits
        self._stack_service = stack_service
        self._location_evaluator = location_evaluator
        self._lock = Lock()
        self._closed = False
        self._active: EpochInspectionSession | None = None
        self._stale_history: dict[str, tuple[InspectionContext, ...]] = {}

    @classmethod
    def create(
        cls,
        index: DebugArtifactIndex,
        read_port: SnapshotReadPort,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
        profile_limits: RecipeLimits,
        stack_service: type[StackService] = StackService,
        location_evaluator: type[LocationEvaluator] = LocationEvaluator,
    ) -> InspectionServiceCreateResult:
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        if not isinstance(profile_limits, RecipeLimits):
            return _failed_create(ResolutionStatus.SCHEMA_UNSUPPORTED, "recipe_profile_limits_mismatch", "profile_limits differ from the accepted recipe profile")
        try:
            binding = index.binding()
            bundle = index.bundle_identity()
        except Exception as exc:
            return _failed_create(ResolutionStatus.CORRUPT, "artifact_index_contract", f"artifact index binding access failed with {type(exc).__name__}")
        validation = DebugBindingValidator.validate(binding, bundle, architecture, abi)
        if validation.status is not ResolutionStatus.RESOLVED:
            return InspectionServiceCreateResult(validation.status, None, validation.diagnostics)
        if binding.payload.accepted_image_debug_capability_profile != _ACCEPTED_PROFILE:
            return _failed_create(ResolutionStatus.SCHEMA_UNSUPPORTED, "inspection_profile_unsupported", "binding capability profile is unsupported")
        return InspectionServiceCreateResult(
            ResolutionStatus.RESOLVED,
            cls(index, read_port, architecture, abi, profile_limits, stack_service, location_evaluator),
            (),
        )

    def active_epoch_id(self) -> StopEpochId | None:
        with self._lock:
            return None if self._active is None else self._active.context().epoch.stop_epoch_id

    def _remember_stale(self, context: InspectionContext) -> None:
        key = context.epoch.stop_epoch_id.value
        values = self._stale_history.get(key, ())
        if context not in values:
            self._stale_history[key] = values + (context,)

    def _classify_foreign_context(self, context: InspectionContext) -> InspectionStatus:
        with self._lock:
            values = self._stale_history.get(context.epoch.stop_epoch_id.value, ())
            return InspectionStatus.STALE if context in values else InspectionStatus.UNKNOWN_HANDLE

    def _validate_open_context(self, context: InspectionContext) -> InspectionOpenResult | None:
        expected = self._index.binding().payload.loaded_image_ref
        if context.target != expected.target_ref:
            return InspectionOpenResult(InspectionOpenStatus.STALE, None, (_diag("inspection_target_stale", "context target differs from bound target"),))
        if context.image.artifact_ref != expected.artifact_ref:
            return InspectionOpenResult(InspectionOpenStatus.ARTIFACT_MISMATCH, None, (_diag("inspection_artifact_mismatch", "context artifact differs from bound artifact"),))
        if context.image != expected:
            return InspectionOpenResult(InspectionOpenStatus.STALE, None, (_diag("inspection_image_stale", "loaded-image identity/generation differs"),))
        return None

    def open_epoch(self, context: InspectionContext, request_limits: RecipeRequestLimits) -> InspectionOpenResult:
        if not isinstance(context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(request_limits, RecipeRequestLimits):
            raise TypeError("request_limits must be RecipeRequestLimits")
        if request_limits.max_frames > self._profile_limits.unwind_frames or request_limits.max_pieces > self._profile_limits.location_pieces:
            return InspectionOpenResult(InspectionOpenStatus.UNAVAILABLE, None, (_diag("limit_exceeded", "epoch request limits exceed profile"),))
        invalid = self._validate_open_context(context)
        if invalid is not None:
            return invalid
        with self._lock:
            if self._closed:
                return InspectionOpenResult(InspectionOpenStatus.UNAVAILABLE, None, (_diag("inspection_service_closed", "inspection service is closed"),))
            epoch_id = context.epoch.stop_epoch_id.value
            if epoch_id in self._stale_history:
                return InspectionOpenResult(InspectionOpenStatus.STALE, None, (_diag("epoch_id_previously_invalidated", "StopEpochId is retained as stale"),))
            if self._active is not None:
                current = self._active.context()
                if current.epoch.stop_epoch_id == context.epoch.stop_epoch_id:
                    if current != context:
                        return InspectionOpenResult(InspectionOpenStatus.STALE, None, (_diag("active_epoch_context_mismatch", "active StopEpochId is bound to another context"),))
                    if self._active.request_limits() != request_limits:
                        return InspectionOpenResult(InspectionOpenStatus.UNAVAILABLE, None, (_diag("epoch_request_limits_conflict", "same epoch is open with different limits"),))
                    return InspectionOpenResult(InspectionOpenStatus.OPENED, self._active, ())
                old = self._active
                old_context = old.context()
                old._invalidate("replaced_by_new_epoch")
                self._remember_stale(old_context)
                self._active = None
            session = EpochInspectionSession(self, context, request_limits, EpochHandleStore.create(context))
            self._active = session
            return InspectionOpenResult(InspectionOpenStatus.OPENED, session, ())

    def invalidate_epoch(self, expected_epoch_id: StopEpochId, reason: str) -> InvalidationResult:
        if not isinstance(expected_epoch_id, StopEpochId):
            raise TypeError("expected_epoch_id must be StopEpochId")
        if not isinstance(reason, str) or not reason:
            raise ValueError("reason must be non-empty")
        with self._lock:
            if self._active is not None and self._active.context().epoch.stop_epoch_id == expected_epoch_id:
                session = self._active
                context = session.context()
                result = session._invalidate(reason)
                self._remember_stale(context)
                self._active = None
                return result
            if expected_epoch_id.value in self._stale_history:
                return InvalidationResult(InvalidationStatus.ALREADY_STALE, expected_epoch_id, (_diag("epoch_already_stale", reason),))
            return InvalidationResult(InvalidationStatus.UNKNOWN_EPOCH, expected_epoch_id, (_diag("unknown_epoch", "StopEpochId is unknown to this service"),))

    def close(self, reason: str) -> ServiceCloseResult:
        if not isinstance(reason, str) or not reason:
            raise ValueError("reason must be non-empty")
        with self._lock:
            if self._closed:
                return ServiceCloseResult(ServiceCloseStatus.ALREADY_CLOSED, None, (_diag("inspection_service_already_closed", reason),))
            invalidation = None
            if self._active is not None:
                context = self._active.context()
                invalidation = self._active._invalidate(reason)
                self._remember_stale(context)
                self._active = None
            self._closed = True
            return ServiceCloseResult(ServiceCloseStatus.CLOSED, invalidation, ())


class EpochInspectionSession:
    def __init__(self, service: InspectionService, context: InspectionContext, request_limits: RecipeRequestLimits, store: EpochHandleStore) -> None:
        self._service = service
        self._context = context
        self._request_limits = request_limits
        self._store = store
        self._lock = Lock()
        self._active = True
        self._revision = 0

    def context(self) -> InspectionContext:
        return self._context

    def request_limits(self) -> RecipeRequestLimits:
        return self._request_limits

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def _invalidate(self, reason: str) -> InvalidationResult:
        with self._lock:
            if not self._active:
                return InvalidationResult(InvalidationStatus.ALREADY_STALE, self._context.epoch.stop_epoch_id, (_diag("epoch_already_stale", reason),))
            self._active = False
            self._revision += 1
            return self._store.invalidate(reason)

    def _begin(self) -> int | None:
        with self._lock:
            return self._revision if self._active else None

    def _finish(self, revision: int) -> bool:
        with self._lock:
            return self._active and self._revision == revision

    def _stale(self):
        return _failure(self._context, InspectionStatus.STALE, "inspection_session_stale", "inspection epoch is stale")

    def _resolve_handle(self, handle: DomainHandle, expected_kind: HandleKind) -> HandleResolution:
        if not isinstance(handle, DomainHandle):
            raise TypeError("handle must be DomainHandle")
        if handle.context != self._context:
            status = self._service._classify_foreign_context(handle.context)
            code = "stale_handle_context" if status is InspectionStatus.STALE else "foreign_handle_context"
            return HandleResolution(status, self._context, expected_kind, None, (_diag(code, "handle context is not active here"),))
        return self._store.resolve(handle, expected_kind)

    def _stack_frames(self):
        return self._service._stack_service.unwind(
            self._context,
            self._service._index,
            self._service._read_port,
            self._service._architecture,
            self._service._abi,
            self._service._profile_limits,
            self._request_limits,
        )

    def _frame_from_handle(self, handle: DomainHandle):
        resolution = self._resolve_handle(handle, HandleKind.FRAME)
        if resolution.status is not InspectionStatus.COMPLETE:
            return None, InspectionResult(resolution.status, self._context, None, resolution.diagnostics)
        frame_index = resolution.object_key[0]
        stack = self._stack_frames()
        if stack.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
            return None, stack
        if frame_index >= len(stack.value):
            return None, _failure(self._context, InspectionStatus.STALE, "frame_no_longer_available", "interned frame is absent from exact snapshot walk")
        return stack.value[frame_index], None

    def registers(self, selection: RegisterSelection) -> InspectionResult[RegisterSet]:
        if not isinstance(selection, RegisterSelection):
            raise TypeError("selection must be RegisterSelection")
        revision = self._begin()
        if revision is None:
            return self._stale()
        coverage = require_snapshot_read_set(self._context, "registers")
        if coverage.status is not InspectionStatus.COMPLETE:
            return InspectionResult(coverage.status, self._context, None, coverage.diagnostics)
        try:
            result = self._service._read_port.read_registers(self._context, selection)
        except Exception as exc:
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", f"register port raised {type(exc).__name__}")
        if not isinstance(result, InspectionResult):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "register port returned non-InspectionResult")
        result = fence_snapshot_result(self._context, result)
        if not self._finish(revision):
            return self._stale()
        if result.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
            return result
        if not isinstance(result.value, RegisterSet):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "register result is not RegisterSet")
        try:
            expected = self._service._architecture.selected_register_order(selection)
        except (TypeError, ValueError, KeyError) as exc:
            return _failure(self._context, InspectionStatus.CORRUPT, "register_selection_invalid", str(exc))
        if tuple(item.register_id for item in result.value.registers) != expected:
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_register_shape_mismatch", "register result identity/order differs")
        for item in result.value.registers:
            if item.bit_width != self._service._architecture.register_bit_width(item.register_id):
                return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_register_width_mismatch", "register width differs from descriptor")
        return result

    def stack(self, page: PageRequest) -> InspectionResult[FramePage]:
        if not isinstance(page, PageRequest):
            raise TypeError("page must be PageRequest")
        revision = self._begin()
        if revision is None:
            return self._stale()
        result = self._stack_frames()
        if result.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
            return result
        if not self._finish(revision):
            return self._stale()
        frames = result.value
        start, end = _page_bounds(len(frames), page)
        records: list[FrameRecord] = []
        with self._lock:
            if not self._active or self._revision != revision:
                return self._stale()
            for frame in frames[start:end]:
                interned = self._store.intern(HandleKind.FRAME, (frame.frame_index,))
                if interned.status is not InspectionStatus.COMPLETE:
                    return InspectionResult(interned.status, self._context, None, interned.diagnostics)
                records.append(FrameRecord(self._context, interned.value, frame))
        return InspectionResult(result.status, self._context, FramePage(len(frames), page.offset, tuple(records)), result.diagnostics)

    def scopes(self, frame_handle: DomainHandle) -> InspectionResult[ScopeSet]:
        revision = self._begin()
        if revision is None:
            return self._stale()
        frame, failed = self._frame_from_handle(frame_handle)
        if failed is not None:
            return failed
        diagnostics: list[Diagnostic] = []
        kinds: list[ScopeKind] = []
        if "registers" in self._context.epoch.snapshot.supported_read_sets:
            kinds.append(ScopeKind.REGISTERS)
        else:
            diagnostics.append(_diag("register_scope_unavailable", "snapshot has no register coverage"))
        if frame.function is not None:
            try:
                lexical = self._service._index.lexical_scopes(frame.function.function_id, frame.pc)
            except Exception as exc:
                lexical = ()
                diagnostics.append(_diag("lexical_scope_contract", f"lookup raised {type(exc).__name__}"))
            if lexical:
                kinds.append(ScopeKind.LOCALS)
            else:
                diagnostics.append(_diag("locals_scope_unavailable", "no lexical scope matches frame"))
        else:
            diagnostics.append(_diag("locals_scope_unavailable", "frame has no exact function"))
        try:
            globals_present = bool(self._service._index.global_variables())
        except Exception as exc:
            globals_present = False
            diagnostics.append(_diag("globals_scope_contract", f"lookup raised {type(exc).__name__}"))
        if globals_present:
            kinds.append(ScopeKind.GLOBALS)
        else:
            diagnostics.append(_diag("globals_scope_unavailable", "artifact contains no globals"))
        if not self._finish(revision):
            return self._stale()
        names = {ScopeKind.REGISTERS: "Registers", ScopeKind.LOCALS: "Locals", ScopeKind.GLOBALS: "Globals"}
        records: list[ScopeRecord] = []
        with self._lock:
            if not self._active or self._revision != revision:
                return self._stale()
            for kind in kinds:
                interned = self._store.intern(HandleKind.SCOPE, (frame_handle.serial, kind))
                if interned.status is not InspectionStatus.COMPLETE:
                    return InspectionResult(interned.status, self._context, None, interned.diagnostics)
                records.append(ScopeRecord(self._context, interned.value, frame_handle, kind, names[kind], False))
        status = InspectionStatus.PARTIAL if diagnostics else InspectionStatus.COMPLETE
        return InspectionResult(status, self._context, ScopeSet(frame_handle, tuple(records)), tuple(diagnostics))

    def _register_expression_value(self, frame: UnwindFrame, register_id: str) -> ExpressionValue:
        architecture = self._service._architecture
        bit_width = architecture.register_bit_width(register_id)
        if register_id in architecture.register_order:
            record = next(item for item in frame.recovered_registers.registers if item.register_id == register_id)
            available, value = record.available, record.unsigned_value
        elif register_id == "PC":
            available, value = True, frame.pc.unsigned_value
        elif register_id == "SP":
            available, value = True, frame.sp.unsigned_value
        elif register_id == "PSW":
            available, value = frame.recovered_psw.available, frame.recovered_psw.unsigned_value
        else:
            raise KeyError(register_id)
        if not available:
            return ExpressionValue(ExpressionKind.REGISTER, register_id, "<unavailable>", None, bit_width, ValueAvailability.UNAVAILABLE, ())
        raw = ScalarBytes.encode(value, False, bit_width, architecture.register_byte_order)
        return ExpressionValue(ExpressionKind.REGISTER, register_id, str(value), raw, bit_width, ValueAvailability.AVAILABLE, ())

    def _symbols_for_scope(self, frame: UnwindFrame, kind: ScopeKind) -> tuple[SymbolRecord, ...]:
        if kind is ScopeKind.GLOBALS:
            return tuple(self._service._index.global_variables())
        if kind is not ScopeKind.LOCALS or frame.function is None:
            return ()
        visible: dict[str, SymbolRecord] = {}
        for scope in self._service._index.lexical_scopes(frame.function.function_id, frame.pc):
            for symbol in self._service._index.variables_in_scope(scope.lexical_scope_id, frame.pc):
                visible[symbol.symbol_id] = symbol
        return tuple(sorted(visible.values(), key=lambda item: (item.declaration_order, item.symbol_id)))

    def _evaluate_symbol(self, frame: UnwindFrame, symbol: SymbolRecord) -> InspectionResult[EvaluatedValue]:
        rows = self._service._index.location_rows(symbol.symbol_id, symbol.function_id, symbol.lexical_scope_id, frame.pc)
        if rows.status is not ResolutionStatus.RESOLVED or len(rows.values) != 1:
            status = InspectionStatus.UNAVAILABLE if rows.status is ResolutionStatus.UNAVAILABLE else InspectionStatus.CORRUPT
            diagnostics = rows.diagnostics or (_diag("location_row_unavailable", "variable has no exact applicable LocationRow"),)
            return InspectionResult(status, self._context, None, diagnostics)
        return self._service._location_evaluator.evaluate(
            self._context,
            frame,
            self._service._index,
            symbol,
            rows.values[0],
            self._service._read_port,
            self._service._architecture,
            self._service._abi,
            self._service._profile_limits,
            self._request_limits,
        )

    def variables(self, scope_handle: DomainHandle, page: PageRequest) -> InspectionResult[VariablePage]:
        if not isinstance(page, PageRequest):
            raise TypeError("page must be PageRequest")
        revision = self._begin()
        if revision is None:
            return self._stale()
        resolution = self._resolve_handle(scope_handle, HandleKind.SCOPE)
        if resolution.status is not InspectionStatus.COMPLETE:
            return InspectionResult(resolution.status, self._context, None, resolution.diagnostics)
        frame_serial, scope_kind = resolution.object_key
        frame_handle = DomainHandle(self._context, HandleKind.FRAME, frame_serial)
        frame, failed = self._frame_from_handle(frame_handle)
        if failed is not None:
            return failed
        pending: list[tuple[str, int, str, object]] = []
        if scope_kind is ScopeKind.REGISTERS:
            for order, register_id in enumerate(self._service._architecture.declared_register_order):
                pending.append(("register", order, register_id, self._register_expression_value(frame, register_id)))
        else:
            try:
                symbols = self._symbols_for_scope(frame, scope_kind)
            except Exception as exc:
                return _failure(self._context, InspectionStatus.CORRUPT, "artifact_index_contract", f"scope lookup raised {type(exc).__name__}")
            for symbol in symbols:
                evaluated = self._evaluate_symbol(frame, symbol)
                if evaluated.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
                    return InspectionResult(evaluated.status, self._context, None, evaluated.diagnostics)
                pending.append(("symbol", symbol.declaration_order, symbol.symbol_id, (symbol, evaluated)))
        if not self._finish(revision):
            return self._stale()
        start, end = _page_bounds(len(pending), page)
        records: list[ScopeValueRecord] = []
        diagnostics: list[Diagnostic] = []
        with self._lock:
            if not self._active or self._revision != revision:
                return self._stale()
            for discriminator, order, identity, payload in pending[start:end]:
                interned = self._store.intern(HandleKind.VARIABLE, (scope_handle.serial, discriminator, order, identity))
                if interned.status is not InspectionStatus.COMPLETE:
                    return InspectionResult(interned.status, self._context, None, interned.diagnostics)
                if discriminator == "register":
                    records.append(RegisterVariableRecord(self._context, interned.value, scope_handle, identity, order, payload))
                else:
                    symbol, evaluated = payload
                    diagnostics.extend(evaluated.diagnostics)
                    records.append(SymbolVariableRecord(self._context, interned.value, scope_handle, symbol.symbol_id, symbol.declaration_order, evaluated.value))
        status = InspectionStatus.PARTIAL if diagnostics else InspectionStatus.COMPLETE
        return InspectionResult(status, self._context, VariablePage(scope_handle, len(pending), page.offset, tuple(records)), tuple(diagnostics))

    def _symbol_by_id(self, symbol_id: str):
        query = getattr(self._service._index, "symbol_by_id", None)
        if query is None or not callable(query):
            return None, _failure(self._context, InspectionStatus.CORRUPT, "artifact_index_contract", "DebugArtifactIndex lacks frozen symbol_by_id query")
        result = query(symbol_id)
        if result.status is not ResolutionStatus.RESOLVED or len(result.values) != 1:
            status = InspectionStatus.UNAVAILABLE if result.status is ResolutionStatus.UNAVAILABLE else InspectionStatus.CORRUPT
            diagnostics = result.diagnostics or (_diag("symbol_id_unavailable", "symbol_id did not resolve exactly once"),)
            return None, InspectionResult(status, self._context, None, diagnostics)
        return result.values[0], None

    def evaluate_snapshot(self, frame_handle: DomainHandle, expression: SnapshotExpression) -> InspectionResult[ExpressionValue]:
        revision = self._begin()
        if revision is None:
            return self._stale()
        frame, failed = self._frame_from_handle(frame_handle)
        if failed is not None:
            return failed
        if isinstance(expression, RegisterExpression):
            try:
                value = self._register_expression_value(frame, expression.register_id)
            except KeyError:
                return _failure(self._context, InspectionStatus.UNAVAILABLE, "register_unavailable", "register is not declared")
        elif isinstance(expression, ConstantExpression):
            raw = ScalarBytes.encode(expression.unsigned_value, False, expression.bit_width, expression.byte_order)
            value = ExpressionValue(ExpressionKind.CONSTANT, None, str(expression.unsigned_value), raw, expression.bit_width, ValueAvailability.AVAILABLE, ())
        elif isinstance(expression, VariableExpression):
            symbol, symbol_failed = self._symbol_by_id(expression.symbol_id)
            if symbol_failed is not None:
                return symbol_failed
            if symbol.kind not in {SymbolKind.LOCAL, SymbolKind.GLOBAL, SymbolKind.CONSTANT} or symbol.function_id != expression.function_id or symbol.lexical_scope_id != expression.lexical_scope_id:
                return _failure(self._context, InspectionStatus.CORRUPT, "variable_identity_mismatch", "VariableExpression differs from exact SymbolRecord")
            evaluated = self._evaluate_symbol(frame, symbol)
            if evaluated.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
                return InspectionResult(evaluated.status, self._context, None, evaluated.diagnostics)
            item = evaluated.value
            value = ExpressionValue(ExpressionKind.VARIABLE, symbol.symbol_id, item.display_value, item.raw_bytes, item.bit_size, item.location_status, item.pieces)
            if not self._finish(revision):
                return self._stale()
            return InspectionResult(evaluated.status, self._context, value, evaluated.diagnostics)
        elif isinstance(expression, SymbolExpression):
            symbol, symbol_failed = self._symbol_by_id(expression.symbol_id)
            if symbol_failed is not None:
                return symbol_failed
            if symbol.kind not in {SymbolKind.FUNCTION, SymbolKind.LABEL} or symbol.address is None:
                return _failure(self._context, InspectionStatus.CORRUPT, "symbol_expression_kind_invalid", "SymbolExpression requires FUNCTION/LABEL")
            descriptor = self._service._architecture.space_descriptor(symbol.address.space)
            checked = self._service._architecture.validate(symbol.address)
            if descriptor is None or checked.status is not AddressStatus.VALID:
                return _failure(self._context, InspectionStatus.CORRUPT, "symbol_address_invalid", "symbol address is invalid")
            raw = ScalarBytes.encode(symbol.address.unsigned_value, False, descriptor.width_bits, descriptor.byte_order)
            value = ExpressionValue(ExpressionKind.SYMBOL, symbol.symbol_id, str(symbol.address.unsigned_value), raw, descriptor.width_bits, ValueAvailability.AVAILABLE, ())
        elif isinstance(expression, MemoryExpression):
            byte_length = (expression.bit_width + 7) // 8
            memory = self.memory(expression.address, byte_length)
            if memory.status is InspectionStatus.PARTIAL:
                return _failure(self._context, InspectionStatus.UNAVAILABLE, "memory_expression_unavailable", "MemoryExpression requires every byte")
            if memory.status is not InspectionStatus.COMPLETE:
                return InspectionResult(memory.status, self._context, None, memory.diagnostics)
            raw = b"".join(segment.data for segment in memory.value.segments)
            display = str(int.from_bytes(raw, byteorder=expression.byte_order.value, signed=False))
            value = ExpressionValue(ExpressionKind.MEMORY, None, display, raw, expression.bit_width, ValueAvailability.AVAILABLE, ())
        else:
            raise TypeError("expression must be one frozen SnapshotExpression variant")
        if not self._finish(revision):
            return self._stale()
        return InspectionResult(InspectionStatus.COMPLETE, self._context, value, ())

    def memory(self, address: HsxAddress, byte_length: int) -> InspectionResult[MemoryBlock]:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 1:
            raise ValueError("byte_length must be an integer >= 1")
        revision = self._begin()
        if revision is None:
            return self._stale()
        units = self._service._architecture.units_for_bytes(address.space, byte_length)
        if units.status is AddressStatus.UNIT_CONVERSION_UNSUPPORTED:
            return _failure(self._context, InspectionStatus.UNSUPPORTED, "unit_conversion_unsupported", units.diagnostics[0].message)
        if units.status is not AddressStatus.VALID:
            return _failure(self._context, InspectionStatus.CORRUPT, "invalid_memory_length", units.diagnostics[0].message)
        checked = self._service._architecture.range(address, units.value, Permission.READ)
        if checked.status is not AddressStatus.VALID:
            return _failure(self._context, InspectionStatus.CORRUPT, "invalid_memory_address", checked.diagnostics[0].message)
        coverage = require_snapshot_read_set(self._context, "memory")
        if coverage.status is not InspectionStatus.COMPLETE:
            return InspectionResult(coverage.status, self._context, None, coverage.diagnostics)
        try:
            result = self._service._read_port.read_memory(self._context, address, byte_length)
        except Exception as exc:
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", f"memory port raised {type(exc).__name__}")
        if not isinstance(result, InspectionResult):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "memory port returned non-InspectionResult")
        result = fence_snapshot_result(self._context, result)
        if not self._finish(revision):
            return self._stale()
        if result.status in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL} and (not isinstance(result.value, MemoryBlock) or result.value.start != address or result.value.requested_length != byte_length):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "memory result does not match exact request")
        return result

    def disassemble(self, address: HsxAddress, instruction_count: int) -> InspectionResult[DisassemblyBlock]:
        if not isinstance(address, HsxAddress):
            raise TypeError("address must be HsxAddress")
        if isinstance(instruction_count, bool) or not isinstance(instruction_count, int) or instruction_count < 1:
            raise ValueError("instruction_count must be an integer >= 1")
        revision = self._begin()
        if revision is None:
            return self._stale()
        checked = self._service._architecture.validate(address, Permission.EXECUTE)
        if address.space != self._service._architecture.pc_space or checked.status is not AddressStatus.VALID:
            return _failure(self._context, InspectionStatus.CORRUPT, "invalid_disassembly_address", "start must be executable pc-space")
        coverage = require_snapshot_read_set(self._context, "disassembly")
        if coverage.status is not InspectionStatus.COMPLETE:
            return InspectionResult(coverage.status, self._context, None, coverage.diagnostics)
        try:
            result = self._service._read_port.read_disassembly(self._context, address, instruction_count)
        except Exception as exc:
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", f"disassembly port raised {type(exc).__name__}")
        if not isinstance(result, InspectionResult):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "disassembly port returned non-InspectionResult")
        result = fence_snapshot_result(self._context, result)
        if not self._finish(revision):
            return self._stale()
        if result.status is not InspectionStatus.COMPLETE:
            return InspectionResult(result.status, self._context, None, result.diagnostics)
        if not isinstance(result.value, tuple) or not all(isinstance(item, InstructionBytes) for item in result.value):
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", "disassembly result must contain InstructionBytes")
        mapped: list[DisassembledInstruction] = []
        for item in result.value:
            metadata_result = self._service._index.instruction_at(item.address)
            metadata = metadata_result.values[0] if metadata_result.status is ResolutionStatus.RESOLVED and len(metadata_result.values) == 1 else None
            mapped.append(DisassembledInstruction(item.address, item.encoded, metadata, None))
        try:
            block = DisassemblyBlock(address, instruction_count, tuple(mapped))
        except (TypeError, ValueError) as exc:
            return _failure(self._context, InspectionStatus.CORRUPT, "snapshot_read_contract", str(exc))
        return InspectionResult(InspectionStatus.COMPLETE, self._context, block, result.diagnostics)


__all__ = [
    "EpochInspectionSession",
    "FramePage",
    "FrameRecord",
    "InspectionOpenResult",
    "InspectionService",
    "InspectionServiceCreateResult",
    "RegisterVariableRecord",
    "ScopeRecord",
    "ScopeSet",
    "ScopeValueRecord",
    "ServiceCloseResult",
    "SymbolVariableRecord",
    "VariablePage",
]
