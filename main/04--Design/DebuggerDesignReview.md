# Debugger Design Review — Protocol Extensions & Symbol Support

**Status:** DRAFT | **Date:** 2025-10-30 | **Owner:** HSX Core  
**Purpose:** Working document to align debugger protocol design across 04.02--Executive.md, 04.09--Debugger.md, and 04.10--TUI_Debugger.md

> This document consolidates design questions and proposed solutions for the HSX debugger system. Once decisions are finalized, changes will be distributed to the respective design documents.

## 1. Symbol Metadata & Disassembly Support

### 1.1 Current State
- **Assembler** (`python/asm.py`): Has `--dump-json` flag that invokes `disassemble.py` to produce JSON with:
  - Instructions with decoded fields (pc, word, mnemonic, operands, rd, rs1, rs2, imm)
  - Labels (text and data) mapped to addresses
  - Symbol annotations for jump targets
  - Data section entries
- **Linker** (`python/hld.py`): Builds unified symbol table from HXO objects, resolves relocations, but does not currently emit debug symbols in HXE
- **TUI Requirements** (04.10): Needs rich disassembly with symbols, function list for breakpoint manager, memory region labels

### 1.2 Design Question: Symbol Metadata Distribution
How should symbol/debug information be made available to the debugger?

**Option A: Separate .sym File (JSON)**
```
app.hxe         # Stripped executable
app.sym         # JSON with symbols, functions, line info
```
- **Pros:**
  - Works for small MCU targets (executive loads only HXE)
  - Desktop debugger loads both files
  - Symbol file can be versioned/distributed separately
  - Easy to strip for production
- **Cons:**
  - Two files to manage
  - Need to ensure version match between HXE and .sym
  
**Option B: Embedded Debug Section (Strippable)**
```
app.hxe with optional .debug section
```
- **Pros:**
  - Single file in development
  - Version mismatch impossible
  - Executive can strip on load for MCU targets
- **Cons:**
  - Larger file size
  - More complex HXE format
  - Executive needs stripping logic

**Option C: Hybrid Approach**
```
app.hxe         # May include minimal symbols (entry points)
app.sym         # Full debug info (optional)
```
- **Pros:**
  - Flexibility: MCU loads stripped HXE, desktop uses both
  - Graceful degradation (debugger works without .sym, but limited)
  - Simple format: HXE unchanged, .sym is standalone JSON
- **Cons:**
  - Still two files for full debugging

**Recommendation:** **Option C (Hybrid)** with .sym JSON format
- Minimal change to existing HXE format
- Executive doesn't need to parse debug sections
- Debugger/TUI loads .sym if available, degrades gracefully if not
- Matches current `--dump-json` pattern

### 1.3 Proposed .sym JSON Schema
```json
{
  "version": 1,
  "hxe_path": "app.hxe",
  "hxe_crc": 0x12345678,
  "symbols": {
    "functions": [
      {
        "name": "main",
        "address": 0x0100,
        "size": 64,
        "file": "main.c",
        "line": 10
      }
    ],
    "variables": [
      {
        "name": "counter",
        "address": 0x2000,
        "size": 4,
        "type": "uint32_t",
        "scope": "global"
      }
    ],
    "labels": {
      "0x0100": ["main", "_start"],
      "0x0120": ["loop_top"],
      "0x0140": ["error_handler"]
    }
  },
  "instructions": [
    {
      "pc": 0x0100,
      "word": 0x01020304,
      "mnemonic": "LDI",
      "operands": "R1, 0x5",
      "file": "main.c",
      "line": 12
    }
  ],
  "memory_regions": [
    {
      "name": "code",
      "start": 0x0000,
      "end": 0x1FFF,
      "type": "text"
    },
    {
      "name": "data",
      "start": 0x2000,
      "end": 0x2FFF,
      "type": "data"
    },
    {
      "name": "stack",
      "start": 0x7000,
      "end": 0x7FFF,
      "type": "stack"
    }
  ]
}
```

### 1.4 Toolchain Changes Required
1. **Linker (`hld.py`)**: Add `--emit-sym` option to generate .sym JSON
2. **Assembler (`asm.py`)**: Preserve source line annotations through to linker
3. **Disassemble (`disassemble.py`)**: Extend JSON schema to match above

## 2. Protocol Extensions for TUI Support

### 2.1 Disassembly API
**Add to 04.09--Debugger.md, Section 5.5 State Inspection:**

```json
// Request
{
  "version": 1,
  "cmd": "disasm.read",
  "session": "<uuid>",
  "pid": 2,
  "addr": 0x1000,
  "count": 20,
  "mode": "around_pc"  // or "from_addr"
}

// Response
{
  "status": "ok",
  "instructions": [
    {
      "pc": 0x0FF8,
      "word": 0x01020304,
      "mnemonic": "LDI",
      "operands": "R1, 0x5",
      "symbol": "main",
      "file": "main.c",
      "line": 12
    }
  ],
  "has_symbols": true
}
```

**Implementation Notes:**
- Executive loads .sym file on task load (if available)
- Caches disassembly and symbol lookups
- `mode: "around_pc"` returns `count/2` instructions before and after current PC
- Falls back to on-the-fly disassembly without symbols if .sym unavailable

### 2.2 Symbol Enumeration API
**Add to 04.09--Debugger.md, Section 5.5 State Inspection:**

```json
// Request
{
  "version": 1,
  "cmd": "symbols.list",
  "session": "<uuid>",
  "pid": 2,
  "type": "function"  // or "variable", "all"
}

// Response
{
  "status": "ok",
  "symbols": [
    {
      "name": "main",
      "address": 0x0100,
      "size": 64,
      "type": "function"
    },
    {
      "name": "init_system",
      "address": 0x0204,
      "size": 32,
      "type": "function"
    }
  ]
}
```

### 2.3 Memory Region Info API
**Add to 04.09--Debugger.md, Section 5.5 State Inspection:**

```json
// Request
{
  "version": 1,
  "cmd": "memory.regions",
  "session": "<uuid>",
  "pid": 2
}

// Response
{
  "status": "ok",
  "regions": [
    {
      "name": "code",
      "start": 0x0000,
      "end": 0x1FFF,
      "type": "text",
      "permissions": "r-x"
    },
    {
      "name": "stack",
      "start": 0x7000,
      "end": 0x7FFF,
      "type": "stack",
      "permissions": "rw-"
    }
  ]
}
```

## 3. Stack Reconstruction Details

### 3.1 Current State
- 04.02--Executive.md mentions "stack reconstruction" but doesn't specify mechanism
- 04.09--Debugger.md shows `stack.info` response format but not implementation

### 3.2 Proposed Implementation (Add to 04.02--Executive.md, Section 5.2)

**Executive Stack Walking Algorithm:**
```python
def reconstruct_stack(pid: int, max_frames: int = 32) -> List[StackFrame]:
    frames = []
    current_pc = vm_reg_get(pid, REG_PC)
    current_sp = vm_reg_get(pid, REG_SP)
    current_fp = vm_reg_get(pid, REG_FP)  # Frame pointer (R14 or similar)
    
    for depth in range(max_frames):
        # Get symbol for current PC
        symbol = symbol_lookup(pid, current_pc)
        
        frame = {
            "depth": depth,
            "pc": current_pc,
            "sp": current_sp,
            "fp": current_fp,
            "symbol": symbol.get("name") if symbol else None,
            "file": symbol.get("file") if symbol else None,
            "line": symbol.get("line") if symbol else None
        }
        frames.append(frame)
        
        # Walk to previous frame using saved FP and return address
        # (Implementation depends on calling convention)
        if current_fp == 0 or current_fp >= stack_limit:
            break
            
        # Read saved return address and frame pointer from stack
        return_addr = vm_mem_read(pid, current_fp - 4, 4)
        prev_fp = vm_mem_read(pid, current_fp, 4)
        
        if return_addr == 0:
            break
            
        current_pc = return_addr
        current_sp = current_fp
        current_fp = prev_fp
    
    return frames
```

**API Specification:**
```json
// Request
{
  "version": 1,
  "cmd": "stack.info",
  "session": "<uuid>",
  "pid": 2,
  "max_frames": 32
}

// Response
{
  "status": "ok",
  "frames": [
    {
      "depth": 0,
      "pc": 0x09F8,
      "sp": 0x7FF0,
      "fp": 0x7FFC,
      "symbol": "mailbox_send",
      "file": "mailbox.c",
      "line": 42
    }
  ]
}
```

## 4. Watch Expression Evaluation

### 4.1 Proposed Implementation (Add to 04.02--Executive.md, Section 5.2)

**Watch Mechanism:**
1. Client issues `watch.add` with symbol name or address expression
2. Executive resolves symbol to memory address using loaded .sym
3. Executive stores watch descriptor: `{watch_id, pid, addr, size, last_value}`
4. On each `trace_step` event, executive checks watched addresses
5. If value changed, emit `watch_update` event

**Watch Descriptor:**
```python
{
  "watch_id": 1,
  "pid": 2,
  "expr": "counter",
  "addr": 0x2000,
  "size": 4,  # bytes
  "type": "uint32_t",  # from symbol info
  "last_value": 0x00000005
}
```

**API Specification (Already in 04.09, clarify implementation):**
```json
// Add watch
Request: {
  "version": 1,
  "cmd": "watch.add",
  "session": "<uuid>",
  "pid": 2,
  "expr": "counter"  // symbol name or address like "0x2000"
}

Response: {
  "status": "ok",
  "watch_id": 1,
  "expr": "counter",
  "addr": 0x2000,
  "size": 4,
  "type": "uint32_t",
  "value": 0x00000005
}
```

**Event on Change:**
```json
{
  "seq": 1234,
  "ts": 1730319687.512,
  "type": "watch_update",
  "pid": 2,
  "data": {
    "watch_id": 1,
    "expr": "counter",
    "old_value": 0x00000005,
    "new_value": 0x00000006,
    "formatted": "6"  // Human-readable based on type
  }
}
```

## 5. Event Schema Refinements

### 5.1 Register Change Tracking
**Optimize `trace_step` event (Add to 04.02--Executive.md, Section 7.2):**

Current:
```json
{
  "seq": 1025,
  "type": "trace_step",
  "pid": 2,
  "data": {
    "pc": 0x09F8,
    "opcode": 0x0372,
    "flags": "Z---"
  }
}
```

Enhanced (optional field):
```json
{
  "seq": 1025,
  "type": "trace_step",
  "pid": 2,
  "data": {
    "pc": 0x09F8,
    "opcode": 0x0372,
    "flags": "Z---",
    "changed_regs": ["R1", "R2", "PC"]  // Optional: only changed registers
  }
}
```

### 5.2 Task State Transitions
**Clarify `scheduler` event (Update 04.02--Executive.md, Section 7.2):**

Current mentions "scheduler" events but schema unclear for individual task state changes.

Enhanced:
```json
{
  "seq": 1030,
  "type": "task_state",
  "pid": 2,
  "data": {
    "prev_state": "running",
    "new_state": "paused",
    "reason": "debug_break"  // or "sleep", "mailbox_wait", "user_pause"
  }
}
```

## 6. Trace Buffer Configuration

### 6.1 Proposed API (Add to 04.09--Debugger.md, Section 5.3)
**Expose trace configuration through session capabilities:**

```json
// During session.open
Request: {
  "version": 1,
  "cmd": "session.open",
  "capabilities": {
    "features": ["events", "stack", "watch", "trace"],
    "trace_buffer_size": 1000,  // Requested buffer size
    "trace_mode": "full"  // or "minimal", "development"
  }
}

Response: {
  "status": "ok",
  "capabilities": {
    "features": ["events", "stack", "watch", "trace"],
    "trace_buffer_size": 1000,  // Negotiated size
    "trace_mode": "full",
    "trace_variant": "desktop_development"  // Executive variant
  }
}
```

### 6.2 Executive Variants (Clarify in 04.02--Executive.md, Section 1.1)
- **Minimal:** No trace buffer, returns only last instruction
- **Development:** Fixed buffer (~100 entries), sufficient for post-mortem
- **Full debugger:** Configurable buffer (100-10000 entries), supports large traces for TUI

## 7. Conditional Breakpoints (Future Enhancement)

### 7.1 Proposed Extension
Not required for initial release, but design protocol with extension in mind:

```json
// Request
{
  "version": 1,
  "cmd": "bp.set",
  "session": "<uuid>",
  "pid": 2,
  "addr": 0x1000,
  "condition": "counter > 10"  // Optional expression
}
```

**Implementation complexity:**
- Requires expression parser in executive
- Performance impact: must evaluate condition on every hit
- **Recommendation:** Defer to v2, use client-side filtering initially

## 8. Document Distribution Plan

Once decisions finalized, distribute changes to:

### 8.1 Updates to 04.02--Executive.md
- **Section 5.2:** Add detailed `disasm.read`, `symbols.list`, `memory.regions` APIs
- **Section 5.2:** Add `stack.info` implementation details (frame walking)
- **Section 5.2:** Add watch expression evaluation mechanism
- **Section 7.2:** Clarify `task_state` event schema
- **Section 7.2:** Add optional `changed_regs` field to `trace_step` events

### 8.2 Updates to 04.09--Debugger.md
- **Section 5.5:** Add new APIs: `disasm.read`, `symbols.list`, `memory.regions`
- **Section 5.6:** Clarify watch implementation details
- **Section 5.1:** Add trace configuration to session capabilities
- **Section 5.2.2:** Add `task_state` event type and `changed_regs` optimization

### 8.3 Updates to 04.10--TUI_Debugger.md
- **Section 2:** Update preconditions to reference .sym file support
- **Section 6.2:** Reference new `disasm.read` API
- **Section 6.4:** Reference new `stack.info` implementation
- **Section 6.6:** Reference watch expression API details

### 8.4 New Toolchain Documentation
- Document .sym JSON schema in `docs/symbol_format.md`
- Update `docs/executive_protocol.md` with new RPC commands

## 9. Open Questions for Discussion

1. **Symbol file format:** Approve .sym JSON schema in Section 1.3?
2. **Disassembly caching:** Should executive cache full disassembly or compute on-demand?
3. **Watch performance:** Acceptable to check all watches on every step, or need optimization?
4. **Trace buffer:** Negotiate size per-session or fixed per executive variant?
5. **Line number info:** Include in every instruction or only at statement boundaries?
6. **ABI/calling convention:** Document frame layout assumptions for stack walking?

## 10. Next Steps

1. **Review this document** with stakeholders
2. **Finalize symbol format** (Section 1.3)
3. **Approve API additions** (Sections 2, 3, 4)
4. **Update design documents** per Section 8
5. **Create implementation issues** for toolchain and executive changes

---

**Change Log:**
- 2025-10-30: Initial draft based on review comments
