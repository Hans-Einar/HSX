"""Snapshot-bound, frontend-neutral stack reconstruction for RF-004.

This module consumes the frozen artifact/recipe/snapshot contracts.  It owns only stack
reconstruction: no frontend handles, caches, runtime adapters, retry policy, or fixed-layout
fallbacks live here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .addresses import (
    AddressArithmeticMode,
    AddressStatus,
    ArchitectureDescriptor,
    HsxAddress,
    Permission,
)
from .artifacts import DebugArtifactIndex
from .identity import AbiDescriptorRef, DebugBindingValidator, InspectionContext
from .metadata import FunctionRecord, SourceLocation
from .recipes import (
    RecipeAddress,
    RecipeBudget,
    RecipeEvaluationContext,
    RecipeEvaluationResult,
    RecipeEvaluationStatus,
    RecipeEvaluator,
    RecipeLimits,
    RecipeRegister,
    RecipeRequestLimits,
    RecipeResultKind,
    RecipeRole,
    RecipeRule,
    RecipeRuleKind,
    RecipeScalar,
    UnwindBoundary,
    UnwindFrame,
    UnwindRow,
)
from .results import (
    Diagnostic,
    InspectionResult,
    InspectionStatus,
    RegisterSelection,
    RegisterSet,
    RegisterValue,
    ResolutionStatus,
)
from .snapshot import SnapshotReadPort, fence_snapshot_result, require_snapshot_read_set


_CURRENT_ABI = "hsx.abi.llc-r7-word32/1"


def _diag(
    code: str,
    message: str,
    *,
    row_id: str | None = None,
    frame_index: int | None = None,
) -> Diagnostic:
    return Diagnostic(
        code,
        message,
        component="stack",
        row_id=row_id,
        frame_index=frame_index,
    )


def _inspection_failure(
    context: InspectionContext,
    status: InspectionStatus,
    diagnostic: Diagnostic,
) -> InspectionResult[tuple[UnwindFrame, ...]]:
    return InspectionResult(status, context, None, (diagnostic,))


def _partial_prefix(
    context: InspectionContext,
    frames: list[UnwindFrame],
    diagnostics: tuple[Diagnostic, ...],
) -> InspectionResult[tuple[UnwindFrame, ...]]:
    if not frames:
        diagnostic = diagnostics[0] if diagnostics else _diag(
            "unwind_unavailable", "no trustworthy frame could be reconstructed"
        )
        return _inspection_failure(context, InspectionStatus.UNAVAILABLE, diagnostic)
    if not diagnostics:
        diagnostics = (_diag("unwind_partial", "unwind stopped after a trustworthy prefix"),)
    return InspectionResult(InspectionStatus.PARTIAL, context, tuple(frames), diagnostics)


def _recipe_status(status: RecipeEvaluationStatus) -> InspectionStatus:
    return {
        RecipeEvaluationStatus.UNAVAILABLE: InspectionStatus.UNAVAILABLE,
        RecipeEvaluationStatus.UNSUPPORTED: InspectionStatus.UNSUPPORTED,
        RecipeEvaluationStatus.CORRUPT: InspectionStatus.CORRUPT,
        RecipeEvaluationStatus.STALE: InspectionStatus.STALE,
        RecipeEvaluationStatus.ARTIFACT_MISMATCH: InspectionStatus.ARTIFACT_MISMATCH,
    }.get(status, InspectionStatus.CORRUPT)


def _resolution_status(status: ResolutionStatus) -> InspectionStatus:
    return {
        ResolutionStatus.UNAVAILABLE: InspectionStatus.UNAVAILABLE,
        ResolutionStatus.ARTIFACT_MISMATCH: InspectionStatus.ARTIFACT_MISMATCH,
        ResolutionStatus.SCHEMA_UNSUPPORTED: InspectionStatus.UNSUPPORTED,
    }.get(status, InspectionStatus.CORRUPT)


@dataclass(slots=True)
class _AggregateBudget:
    opcodes_remaining: int
    bytes_remaining: int

    @classmethod
    def create(cls, limits: RecipeLimits) -> _AggregateBudget:
        return cls(limits.unwind_total_opcodes, limits.unwind_total_dereferenced_bytes)

    def evaluate(
        self,
        evaluation: RecipeEvaluationContext,
        expression,
        read_port: SnapshotReadPort,
        limits: RecipeLimits,
    ) -> RecipeEvaluationResult:
        budget = RecipeBudget(
            min(limits.opcodes_per_expression, self.opcodes_remaining),
            limits.dereferences_per_expression,
            self.bytes_remaining,
        )
        result = RecipeEvaluator.evaluate(
            evaluation,
            expression,
            read_port,
            limits,
            budget,
        )
        consumed_opcodes = budget.opcodes_remaining - result.budget_after.opcodes_remaining
        consumed_bytes = budget.bytes_remaining - result.budget_after.bytes_remaining
        self.opcodes_remaining -= consumed_opcodes
        self.bytes_remaining -= consumed_bytes
        return result


@dataclass(frozen=True, slots=True)
class _FrameSeed:
    pc: HsxAddress
    sp: HsxAddress
    recovered_registers: RegisterSet
    recovered_psw: RegisterValue
    frame_base: HsxAddress | None
    resume_pc: HsxAddress | None
    call_site_pc: HsxAddress | None
    diagnostics: tuple[Diagnostic, ...] = ()


def _validate_profile_request(
    context: InspectionContext,
    profile_limits: RecipeLimits,
    request_limits: RecipeRequestLimits,
) -> InspectionResult[tuple[UnwindFrame, ...]] | None:
    if not isinstance(profile_limits, RecipeLimits):
        raise TypeError("profile_limits must be RecipeLimits")
    if not isinstance(request_limits, RecipeRequestLimits):
        raise TypeError("request_limits must be RecipeRequestLimits")
    if (
        request_limits.max_frames > profile_limits.unwind_frames
        or request_limits.max_pieces > profile_limits.location_pieces
    ):
        return _inspection_failure(
            context,
            InspectionStatus.UNSUPPORTED,
            _diag("limit_exceeded", "request limits exceed the accepted recipe profile"),
        )
    return None


def _validate_binding(
    context: InspectionContext,
    index: DebugArtifactIndex,
    architecture: ArchitectureDescriptor,
    abi: AbiDescriptorRef,
) -> tuple[object | None, object | None, InspectionResult[tuple[UnwindFrame, ...]] | None]:
    try:
        binding = index.binding()
        bundle_identity = index.bundle_identity()
    except Exception as exc:
        return None, None, _inspection_failure(
            context,
            InspectionStatus.ARTIFACT_MISMATCH,
            _diag(
                "artifact_index_contract",
                f"artifact index binding access failed with {type(exc).__name__}",
            ),
        )
    try:
        validation = DebugBindingValidator.validate(binding, bundle_identity, architecture, abi)
    except (TypeError, ValueError) as exc:
        return None, None, _inspection_failure(
            context,
            InspectionStatus.ARTIFACT_MISMATCH,
            _diag("debug_binding_contract", str(exc)),
        )
    if validation.status is not ResolutionStatus.RESOLVED:
        diagnostic = validation.diagnostics[0] if validation.diagnostics else _diag(
            "debug_binding_mismatch", "debug binding validation failed"
        )
        return None, None, InspectionResult(
            _resolution_status(validation.status), context, None, (diagnostic,)
        )
    if binding.payload.loaded_image_ref != context.image:
        return None, None, _inspection_failure(
            context,
            InspectionStatus.ARTIFACT_MISMATCH,
            _diag(
                "binding_loaded_image_mismatch",
                "inspection context image differs from the debug binding",
            ),
        )
    return binding, bundle_identity, None


def _validated_address(
    architecture: ArchitectureDescriptor,
    register: RegisterValue,
    space,
    *,
    permission: Permission | None,
    code: str,
) -> tuple[HsxAddress | None, Diagnostic | None]:
    if not register.available:
        return None, _diag(code, f"{register.register_id} is unavailable in the snapshot")
    address = HsxAddress(space, register.unsigned_value)
    result = architecture.validate(address, permission)
    if result.status is not AddressStatus.VALID:
        message = result.diagnostics[0].message if result.diagnostics else "invalid address evidence"
        return None, _diag(code, message)
    return address, None


def _read_top_seed(
    context: InspectionContext,
    read_port: SnapshotReadPort,
    architecture: ArchitectureDescriptor,
    abi: AbiDescriptorRef,
) -> tuple[_FrameSeed | None, InspectionResult[tuple[UnwindFrame, ...]] | None]:
    coverage = require_snapshot_read_set(context, "registers")
    if coverage.status is not InspectionStatus.COMPLETE:
        return None, InspectionResult(
            coverage.status,
            context,
            None,
            coverage.diagnostics,
        )
    selection = RegisterSelection(True, ())
    try:
        result = read_port.read_registers(context, selection)
    except Exception as exc:
        return None, _inspection_failure(
            context,
            InspectionStatus.CORRUPT,
            _diag("snapshot_read_contract", f"snapshot register port raised {type(exc).__name__}"),
        )
    if not isinstance(result, InspectionResult):
        return None, _inspection_failure(
            context,
            InspectionStatus.CORRUPT,
            _diag("snapshot_read_contract", "snapshot register port returned a non-InspectionResult"),
        )
    result = fence_snapshot_result(context, result)
    if result.status not in {InspectionStatus.COMPLETE, InspectionStatus.PARTIAL}:
        diagnostic = result.diagnostics[0] if result.diagnostics else _diag(
            "snapshot_registers_unavailable", "snapshot registers are unavailable"
        )
        return None, InspectionResult(result.status, context, None, (diagnostic,))
    registers = result.value
    if not isinstance(registers, RegisterSet):
        return None, _inspection_failure(
            context,
            InspectionStatus.CORRUPT,
            _diag("snapshot_read_contract", "snapshot register result is not RegisterSet"),
        )
    expected = architecture.declared_register_order
    actual = tuple(item.register_id for item in registers.registers)
    if actual != expected:
        return None, _inspection_failure(
            context,
            InspectionStatus.CORRUPT,
            _diag(
                "snapshot_register_shape_mismatch",
                "all-declared register result must exactly follow descriptor order",
            ),
        )
    by_id = {item.register_id: item for item in registers.registers}
    for register_id in expected:
        if by_id[register_id].bit_width != architecture.register_bit_width(register_id):
            return None, _inspection_failure(
                context,
                InspectionStatus.CORRUPT,
                _diag(
                    "snapshot_register_width_mismatch",
                    f"snapshot register {register_id} has the wrong width",
                ),
            )

    pc, pc_error = _validated_address(
        architecture,
        by_id["PC"],
        architecture.pc_space,
        permission=Permission.EXECUTE,
        code="top_pc_unavailable",
    )
    sp, sp_error = _validated_address(
        architecture,
        by_id["SP"],
        architecture.sp_space,
        permission=None,
        code="top_sp_unavailable",
    )
    if pc is None or sp is None:
        diagnostic = pc_error if pc is None else sp_error
        return None, _inspection_failure(context, InspectionStatus.UNAVAILABLE, diagnostic)

    gprs = RegisterSet(tuple(by_id[item] for item in architecture.register_order))
    psw = by_id["PSW"]
    diagnostics = list(result.diagnostics)
    frame_base = None
    if abi.ref == _CURRENT_ABI and "R7" in by_id and by_id["R7"].available:
        candidate = HsxAddress(architecture.sp_space, by_id["R7"].unsigned_value)
        checked = architecture.validate(candidate)
        if checked.status is AddressStatus.VALID:
            frame_base = candidate
        else:
            diagnostics.append(
                _diag(
                    "top_frame_base_unavailable",
                    checked.diagnostics[0].message if checked.diagnostics else "R7 is not a valid frame-base address",
                    frame_index=0,
                )
            )

    return (
        _FrameSeed(
            pc=pc,
            sp=sp,
            recovered_registers=gprs,
            recovered_psw=psw,
            frame_base=frame_base,
            resume_pc=None,
            call_site_pc=None,
            diagnostics=tuple(diagnostics),
        ),
        None,
    )


def _annotations(index: DebugArtifactIndex, pc: HsxAddress) -> tuple[
    FunctionRecord | None, SourceLocation | None, tuple[Diagnostic, ...]
]:
    diagnostics: list[Diagnostic] = []
    try:
        functions = tuple(item for item in index.functions() if item.range.contains(pc))
    except Exception as exc:
        functions = ()
        diagnostics.append(
            _diag("function_index_contract", f"function enumeration failed with {type(exc).__name__}")
        )
    function = functions[0] if len(functions) == 1 else None
    if len(functions) > 1:
        diagnostics.append(
            _diag("function_ambiguous", "more than one function contains the frame PC")
        )

    source = None
    try:
        instruction = index.instruction_at(pc)
    except Exception as exc:
        diagnostics.append(
            _diag("instruction_index_contract", f"instruction lookup failed with {type(exc).__name__}")
        )
    else:
        if instruction.status is ResolutionStatus.RESOLVED and len(instruction.values) == 1:
            source = instruction.values[0].source
        elif instruction.status not in {ResolutionStatus.UNAVAILABLE}:
            diagnostics.extend(instruction.diagnostics)
    return function, source, tuple(diagnostics)


def _evaluation_context(
    context: InspectionContext,
    binding,
    bundle_identity,
    architecture: ArchitectureDescriptor,
    abi: AbiDescriptorRef,
    frame_index: int,
    seed: _FrameSeed,
    cfa: HsxAddress | None,
) -> RecipeEvaluationContext:
    psw = seed.recovered_psw
    return RecipeEvaluationContext(
        context=context,
        frame_index=frame_index,
        binding=binding,
        bundle_identity=bundle_identity,
        architecture=architecture,
        abi=abi,
        pc=seed.pc,
        sp=seed.sp,
        psw=(RecipeScalar(False, psw.bit_width, psw.unsigned_value) if psw.available else None),
        recovered_registers=seed.recovered_registers,
        cfa=cfa,
        frame_base=seed.frame_base,
    )


def _required_address_rule(
    rule: RecipeRule,
    *,
    same_value: HsxAddress,
    evaluation: RecipeEvaluationContext,
    read_port: SnapshotReadPort,
    limits: RecipeLimits,
    aggregate: _AggregateBudget,
    role: RecipeRole,
    row_id: str,
    frame_index: int,
) -> tuple[HsxAddress | None, RecipeEvaluationStatus | None, tuple[Diagnostic, ...]]:
    if rule.kind is RecipeRuleKind.SAME:
        return same_value, None, ()
    if rule.kind is not RecipeRuleKind.EXPRESSION:
        reason = rule.reason or rule.kind.value
        return None, RecipeEvaluationStatus.UNAVAILABLE, (
            _diag(
                "caller_state_unavailable",
                f"{role.value} is {reason}",
                row_id=row_id,
                frame_index=frame_index,
            ),
        )
    result = aggregate.evaluate(evaluation, rule.expression, read_port, limits)
    if result.status is not RecipeEvaluationStatus.COMPLETE:
        return None, result.status, result.diagnostics
    if not isinstance(result.value, RecipeAddress):
        return None, RecipeEvaluationStatus.CORRUPT, (
            _diag(
                "invalid_caller_rule_result",
                f"{role.value} did not evaluate to RecipeAddress",
                row_id=row_id,
                frame_index=frame_index,
            ),
        )
    return result.value.address, None, result.diagnostics


def _optional_frame_base_rule(
    rule: RecipeRule | None,
    *,
    current: HsxAddress | None,
    evaluation: RecipeEvaluationContext,
    read_port: SnapshotReadPort,
    limits: RecipeLimits,
    aggregate: _AggregateBudget,
    row_id: str,
    frame_index: int,
) -> tuple[HsxAddress | None, RecipeEvaluationStatus | None, tuple[Diagnostic, ...]]:
    if rule is None:
        return None, None, ()
    if rule.kind is RecipeRuleKind.SAME:
        return current, None, ()
    if rule.kind is not RecipeRuleKind.EXPRESSION:
        return None, None, ()
    result = aggregate.evaluate(evaluation, rule.expression, read_port, limits)
    if result.status is RecipeEvaluationStatus.UNAVAILABLE:
        return None, None, result.diagnostics
    if result.status is not RecipeEvaluationStatus.COMPLETE:
        return None, result.status, result.diagnostics
    if not isinstance(result.value, RecipeAddress):
        return None, RecipeEvaluationStatus.CORRUPT, (
            _diag(
                "invalid_caller_frame_base_result",
                "caller_frame_base did not evaluate to RecipeAddress",
                row_id=row_id,
                frame_index=frame_index,
            ),
        )
    return result.value.address, None, result.diagnostics


def _recover_gprs(
    row: UnwindRow,
    *,
    current: RegisterSet,
    evaluation: RecipeEvaluationContext,
    read_port: SnapshotReadPort,
    architecture: ArchitectureDescriptor,
    limits: RecipeLimits,
    aggregate: _AggregateBudget,
    frame_index: int,
) -> tuple[RegisterSet | None, RecipeEvaluationStatus | None, tuple[Diagnostic, ...]]:
    current_by_id = {item.register_id: item for item in current.registers}
    rules = {register_id: rule for register_id, rule in row.register_rules}
    recovered: list[RegisterValue] = []
    diagnostics: list[Diagnostic] = []

    for register_id in architecture.register_order:
        rule = rules.get(register_id)
        if rule is None:
            recovered.append(RegisterValue(register_id, architecture.register_width_bits, None, False))
            continue
        if rule.kind is RecipeRuleKind.SAME:
            younger = current_by_id.get(register_id)
            if younger is None:
                return None, RecipeEvaluationStatus.CORRUPT, (
                    _diag(
                        "same_register_missing",
                        f"SAME rule has no younger-frame {register_id} evidence",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
            recovered.append(younger)
            continue
        if rule.kind is not RecipeRuleKind.EXPRESSION:
            recovered.append(RegisterValue(register_id, architecture.register_width_bits, None, False))
            continue

        result = aggregate.evaluate(evaluation, rule.expression, read_port, limits)
        if result.status is RecipeEvaluationStatus.UNAVAILABLE:
            diagnostics.extend(result.diagnostics)
            recovered.append(RegisterValue(register_id, architecture.register_width_bits, None, False))
            continue
        if result.status is not RecipeEvaluationStatus.COMPLETE:
            return None, result.status, result.diagnostics

        value = result.value
        if isinstance(value, RecipeRegister):
            if (
                value.register_id != register_id
                or value.bit_width != architecture.register_width_bits
            ):
                return None, RecipeEvaluationStatus.CORRUPT, (
                    _diag(
                        "invalid_register_rule_result",
                        "REGISTER result identity/width differs from the row key",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
            bits = value.unsigned_value
        elif isinstance(value, RecipeScalar):
            if value.signed or value.bit_width != architecture.register_width_bits:
                return None, RecipeEvaluationStatus.CORRUPT, (
                    _diag(
                        "invalid_register_rule_result",
                        "scalar GPR result must be exact-width unsigned",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
            bits = value.value
        else:
            return None, RecipeEvaluationStatus.CORRUPT, (
                _diag(
                    "invalid_register_rule_result",
                    "GPR expression returned a non-register/non-scalar value",
                    row_id=row.row_id,
                    frame_index=frame_index,
                ),
            )
        recovered.append(
            RegisterValue(register_id, architecture.register_width_bits, bits, True)
        )

    return RegisterSet(tuple(recovered)), None, tuple(diagnostics)


def _checked_call_site(
    resume_pc: HsxAddress,
    row: UnwindRow,
    index: DebugArtifactIndex,
    architecture: ArchitectureDescriptor,
    frame_index: int,
) -> tuple[HsxAddress | None, tuple[Diagnostic, ...]]:
    adjustment = row.call_site_adjustment
    if adjustment is None:
        return None, ()
    if adjustment == 0:
        candidate = resume_pc
    elif adjustment < 0:
        checked = architecture.subtract(
            resume_pc, -adjustment, AddressArithmeticMode.CHECKED
        )
        if checked.status is not AddressStatus.VALID:
            return None, (
                _diag(
                    "call_site_unavailable",
                    checked.diagnostics[0].message if checked.diagnostics else "call-site subtraction failed",
                    row_id=row.row_id,
                    frame_index=frame_index,
                ),
            )
        candidate = checked.value
    else:
        checked = architecture.add(
            resume_pc, adjustment, AddressArithmeticMode.CHECKED
        )
        if checked.status is not AddressStatus.VALID:
            return None, (
                _diag(
                    "call_site_unavailable",
                    checked.diagnostics[0].message if checked.diagnostics else "call-site addition failed",
                    row_id=row.row_id,
                    frame_index=frame_index,
                ),
            )
        candidate = checked.value

    executable = architecture.validate(candidate, Permission.EXECUTE)
    if executable.status is not AddressStatus.VALID:
        return None, (
            _diag(
                "call_site_unavailable",
                executable.diagnostics[0].message if executable.diagnostics else "call-site PC is not executable",
                row_id=row.row_id,
                frame_index=frame_index,
            ),
        )
    try:
        instruction = index.instruction_at(candidate)
    except Exception as exc:
        return None, (
            _diag(
                "call_site_unavailable",
                f"call-site instruction lookup failed with {type(exc).__name__}",
                row_id=row.row_id,
                frame_index=frame_index,
            ),
        )
    if instruction.status is not ResolutionStatus.RESOLVED or len(instruction.values) != 1:
        diagnostics = instruction.diagnostics or (
            _diag(
                "call_site_unavailable",
                "call-site adjustment does not name one exact instruction",
                row_id=row.row_id,
                frame_index=frame_index,
            ),
        )
        return None, tuple(diagnostics)
    return candidate, ()


class StackService:
    """Pure snapshot-bound stack walk over verified artifact recipes."""

    @staticmethod
    def unwind(
        context: InspectionContext,
        index: DebugArtifactIndex,
        read_port: SnapshotReadPort,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
        profile_limits: RecipeLimits,
        request_limits: RecipeRequestLimits,
    ) -> InspectionResult[tuple[UnwindFrame, ...]]:
        if not isinstance(context, InspectionContext):
            raise TypeError("context must be InspectionContext")
        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")

        limit_failure = _validate_profile_request(context, profile_limits, request_limits)
        if limit_failure is not None:
            return limit_failure
        binding, bundle_identity, binding_failure = _validate_binding(
            context, index, architecture, abi
        )
        if binding_failure is not None:
            return binding_failure

        seed, seed_failure = _read_top_seed(context, read_port, architecture, abi)
        if seed_failure is not None:
            return seed_failure

        aggregate = _AggregateBudget.create(profile_limits)
        frames: list[UnwindFrame] = []
        seen_frame_keys: set[tuple[object, int, object, int]] = set()
        seen_cfas: set[tuple[object, int]] = set()
        current = seed

        for frame_index in range(request_limits.max_frames):
            key = (
                current.pc.space,
                current.pc.unsigned_value,
                current.sp.space,
                current.sp.unsigned_value,
            )
            if key in seen_frame_keys:
                return _inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    _diag(
                        "unwind_cycle",
                        "frame PC/SP pair repeated during unwind",
                        frame_index=frame_index,
                    ),
                )
            seen_frame_keys.add(key)

            function, source, annotation_diagnostics = _annotations(index, current.pc)
            function_id = function.function_id if function is not None else None
            try:
                row_result = index.unwind_rows(current.pc, function_id)
            except Exception as exc:
                return _inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    _diag(
                        "unwind_index_contract",
                        f"unwind row lookup failed with {type(exc).__name__}",
                        frame_index=frame_index,
                    ),
                )
            if row_result.status is not ResolutionStatus.RESOLVED or len(row_result.values) != 1:
                diagnostics = row_result.diagnostics or (
                    _diag(
                        "unwind_row_unavailable",
                        "no exact unwind row matched the selected frame",
                        frame_index=frame_index,
                    ),
                )
                status = _resolution_status(row_result.status)
                if status is InspectionStatus.UNAVAILABLE and frames:
                    return _partial_prefix(context, frames, tuple(diagnostics))
                return InspectionResult(status, context, None, tuple(diagnostics))
            row = row_result.values[0]
            if not isinstance(row, UnwindRow) or row.abi != abi or row.binding != binding:
                return _inspection_failure(
                    context,
                    InspectionStatus.ARTIFACT_MISMATCH,
                    _diag(
                        "unwind_row_binding_mismatch",
                        "selected unwind row differs from the validated binding/ABI",
                        frame_index=frame_index,
                    ),
                )
            if row.boundary is UnwindBoundary.UNSUPPORTED:
                return _inspection_failure(
                    context,
                    InspectionStatus.UNSUPPORTED,
                    _diag(
                        "unwind_boundary_unsupported",
                        "selected unwind row explicitly marks this boundary unsupported",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )

            base_evaluation = _evaluation_context(
                context,
                binding,
                bundle_identity,
                architecture,
                abi,
                frame_index,
                current,
                None,
            )
            cfa_result = aggregate.evaluate(
                base_evaluation,
                row.cfa_expression,
                read_port,
                profile_limits,
            )
            if cfa_result.status is not RecipeEvaluationStatus.COMPLETE:
                status = _recipe_status(cfa_result.status)
                if status is InspectionStatus.UNAVAILABLE and frames:
                    return _partial_prefix(context, frames, cfa_result.diagnostics)
                diagnostics = cfa_result.diagnostics or (
                    _diag(
                        "cfa_unavailable",
                        "CFA evaluation did not complete",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
                return InspectionResult(status, context, None, diagnostics)
            if not isinstance(cfa_result.value, RecipeAddress):
                return _inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    _diag(
                        "invalid_cfa_result",
                        "CFA recipe returned a non-address value",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
            cfa = cfa_result.value.address
            cfa_key = (cfa.space, cfa.unsigned_value)
            if cfa_key in seen_cfas:
                return _inspection_failure(
                    context,
                    InspectionStatus.CORRUPT,
                    _diag(
                        "cyclic_cfa",
                        "CFA address repeated during unwind",
                        row_id=row.row_id,
                        frame_index=frame_index,
                    ),
                )
            seen_cfas.add(cfa_key)

            frame_diagnostics = tuple(
                current.diagnostics + annotation_diagnostics + cfa_result.diagnostics
            )
            frame = UnwindFrame(
                context=context,
                frame_index=frame_index,
                pc=current.pc,
                sp=current.sp,
                cfa=cfa,
                recovered_registers=current.recovered_registers,
                recovered_psw=current.recovered_psw,
                frame_base=current.frame_base,
                resume_pc=current.resume_pc,
                call_site_pc=current.call_site_pc,
                function=function,
                source=source,
                terminal=row.boundary is UnwindBoundary.TERMINAL,
                diagnostics=frame_diagnostics,
            )
            frames.append(frame)

            if row.boundary is UnwindBoundary.TERMINAL:
                return InspectionResult(InspectionStatus.COMPLETE, context, tuple(frames), ())
            if frame_index + 1 >= request_limits.max_frames:
                return InspectionResult(InspectionStatus.COMPLETE, context, tuple(frames), ())

            evaluation = _evaluation_context(
                context,
                binding,
                bundle_identity,
                architecture,
                abi,
                frame_index,
                current,
                cfa,
            )
            caller_pc, pc_status, pc_diagnostics = _required_address_rule(
                row.caller_pc_rule,
                same_value=current.pc,
                evaluation=evaluation,
                read_port=read_port,
                limits=profile_limits,
                aggregate=aggregate,
                role=RecipeRole.CALLER_PC,
                row_id=row.row_id,
                frame_index=frame_index,
            )
            if pc_status is not None:
                status = _recipe_status(pc_status)
                if status is InspectionStatus.UNAVAILABLE:
                    return _partial_prefix(context, frames, pc_diagnostics)
                return InspectionResult(status, context, None, pc_diagnostics)

            caller_sp, sp_status, sp_diagnostics = _required_address_rule(
                row.caller_sp_rule,
                same_value=current.sp,
                evaluation=evaluation,
                read_port=read_port,
                limits=profile_limits,
                aggregate=aggregate,
                role=RecipeRole.CALLER_SP,
                row_id=row.row_id,
                frame_index=frame_index,
            )
            if sp_status is not None:
                status = _recipe_status(sp_status)
                if status is InspectionStatus.UNAVAILABLE:
                    return _partial_prefix(context, frames, sp_diagnostics)
                return InspectionResult(status, context, None, sp_diagnostics)

            caller_frame_base, base_status, base_diagnostics = _optional_frame_base_rule(
                row.caller_frame_base_rule,
                current=current.frame_base,
                evaluation=evaluation,
                read_port=read_port,
                limits=profile_limits,
                aggregate=aggregate,
                row_id=row.row_id,
                frame_index=frame_index,
            )
            if base_status is not None:
                return InspectionResult(
                    _recipe_status(base_status), context, None, base_diagnostics
                )

            caller_gprs, gpr_status, gpr_diagnostics = _recover_gprs(
                row,
                current=current.recovered_registers,
                evaluation=evaluation,
                read_port=read_port,
                architecture=architecture,
                limits=profile_limits,
                aggregate=aggregate,
                frame_index=frame_index,
            )
            if gpr_status is not None:
                return InspectionResult(
                    _recipe_status(gpr_status), context, None, gpr_diagnostics
                )

            call_site_pc, call_site_diagnostics = _checked_call_site(
                caller_pc,
                row,
                index,
                architecture,
                frame_index,
            )
            next_pc = call_site_pc if call_site_pc is not None else caller_pc
            next_psw = RegisterValue("PSW", architecture.psw_width_bits, None, False)
            current = _FrameSeed(
                pc=next_pc,
                sp=caller_sp,
                recovered_registers=caller_gprs,
                recovered_psw=next_psw,
                frame_base=caller_frame_base,
                resume_pc=caller_pc,
                call_site_pc=call_site_pc,
                diagnostics=tuple(
                    pc_diagnostics
                    + sp_diagnostics
                    + base_diagnostics
                    + gpr_diagnostics
                    + call_site_diagnostics
                ),
            )

        return InspectionResult(InspectionStatus.COMPLETE, context, tuple(frames), ())


__all__ = ["StackService"]
