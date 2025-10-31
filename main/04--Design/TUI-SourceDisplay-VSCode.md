# TUI Source Display & VS Code Integration
**Status:** DRAFT | **Date:** 2025-10-31 | **Owner:** HSX Core  
**Purpose:** Design supplement for source file display in TUI and VS Code Debug Adapter Protocol integration

> This document addresses additional TUI debugger requirements: source file display, configurable window layouts, source path handling, and VS Code integration via Debug Adapter Protocol (DAP).

## 1. Source File Display in TUI

### 1.1 Overview
Adding a source file viewer panel to the TUI debugger enables developers to see the actual C/C++ source code alongside disassembly, stepping through code at the source level rather than instruction level.

### 1.2 Source Panel Design

**Panel Features:**
- Display source file contents with syntax highlighting
- Highlight current execution line (from PC → line mapping in .sym)
- Show breakpoints in source gutter
- Scroll to follow execution or allow manual navigation
- Toggle between source and disassembly views

**Mockup:**
```
┌─────────────────────────┬──────────────────────────────────────┬───────────────────────────────┐
│ Source: main.c          │ Execution Trace                     │ Registers (PID 2)             │
│─────────────────────────│──────────────────────────────────────│───────────────────────────────│
│   8  int main(void) {   │ ▶ 0x09F8: ST  R7 + -4 ← R2           │ PC : 0x09F8                   │
│   9      int x = 5;     │   0x09FC: ST  R7 + -16 ← R1          │ SP : 0x7FF0                   │
│  10      int y = 10;    │   0x0A00: LD  R9 ← MEM[R7 + -4]      │ R0 : 0x00000000               │
│● 11      int z = x + y; │   0x0A04: ST  R7 + -20 ← R9          │ R1 : 0x000040EF               │
│▶ 12      return z;      │   0x0A08: JMP 0x0A10                 │ R2 : 0x00000005               │
│  13  }                  │   0x0A10: LD  R4 ← MEM[R7 + -20]     │ ...                           │
│                         │                                      │                               │
│ [main.c:12]             │                                      │                               │
├─────────────────────────┴──────────────────────────────────────┴───────────────────────────────┤
│ [Alt+S] Step Source  [Alt+I] Step Instruction  [Alt+V] Toggle Source/Disasm                    │
└────────────────────────────────────────────────────────────────────────────────────────────────┘

Legend:
● = Breakpoint at line 11
▶ = Current execution line (PC = 0x09F8 → main.c:12)
```

**Implementation:**
- Query executive for current PC via existing `reg.get` API
- Look up source file and line from .sym file: `instructions[pc] → {file, line}`
- Load source file from filesystem
- Display with current line highlighted
- Update on `trace_step` events

**Panel State:**
```python
class SourcePanel:
    def __init__(self):
        self.current_file = None
        self.file_contents = {}  # Cache loaded files
        self.current_line = None
        self.scroll_offset = 0
        self.breakpoints = set()  # Set of (file, line) tuples
    
    def update_from_pc(self, pc: int):
        """Update source view based on current PC"""
        # Look up source location from .sym
        loc = self.symbol_table.lookup_line(pc)
        if loc:
            if loc['file'] != self.current_file:
                self.load_source_file(loc['file'])
            self.current_line = loc['line']
            self.scroll_to_line(self.current_line)
```

### 1.3 Source File Loading

**File Resolution:**
1. .sym file contains path to source file (relative or absolute)
2. TUI searches for file in multiple locations:
   - Exact path from .sym (if absolute and exists)
   - Relative to .sym file location
   - Relative to project root (configured)
   - Source search paths (configured)

**Configuration:**
```json
{
  "source_paths": [
    "/home/user/project",
    "/home/user/project/src",
    "./relative/path"
  ],
  "source_map": {
    "/old/path": "/new/path"
  }
}
```

**Error Handling:**
- If source file not found, show message: "Source file not available: main.c"
- Fall back to disassembly-only view
- Allow user to specify source location interactively

### 1.4 Syntax Highlighting

**Using `rich` library (already a dependency via Textual):**
```python
from rich.syntax import Syntax

def render_source(file_path: str, current_line: int):
    """Render source with syntax highlighting"""
    with open(file_path) as f:
        code = f.read()
    
    syntax = Syntax(
        code,
        "c",  # or auto-detect from extension
        theme="monokai",
        line_numbers=True,
        highlight_lines={current_line}
    )
    return syntax
```

### 1.5 Source-Level Stepping

**Step Source (Alt+S):**
- Issue `step` commands until PC crosses source line boundary
- Query .sym for next source line after each instruction step
- Stop when `line` field changes

**Step Instruction (Alt+I):**
- Single instruction step (existing behavior)
- Useful for examining generated code

**Run to Line:**
- Set temporary breakpoint at target line (resolve to PC via .sym)
- Continue execution
- Remove temporary breakpoint on hit

## 2. Configurable Window Layouts

### 2.1 Layout Configuration File

**Format:** YAML or JSON configuration file

**Example (`~/.hsxdbg/layout.yaml`):**
```yaml
version: 1
default_layout: "debug_full"

layouts:
  debug_full:
    name: "Full Debug Layout"
    panels:
      - type: "source"
        position: {row: 0, col: 0, width: 40, height: 20}
        config:
          show_line_numbers: true
          syntax_highlighting: true
      
      - type: "registers"
        position: {row: 0, col: 40, width: 20, height: 10}
        config:
          show_flags: true
          format: "hex"
      
      - type: "disassembly"
        position: {row: 0, col: 60, width: 40, height: 20}
        config:
          show_symbols: true
          show_addresses: true
      
      - type: "trace"
        position: {row: 10, col: 40, width: 20, height: 10}
        config:
          max_entries: 100
      
      - type: "stack"
        position: {row: 20, col: 0, width: 50, height: 10}
        config:
          max_depth: 10
      
      - type: "watch"
        position: {row: 20, col: 50, width: 50, height: 10}
      
      - type: "console"
        position: {row: 30, col: 0, width: 100, height: 10}
    
    status_bar:
      enabled: true
      position: "bottom"
  
  compact:
    name: "Compact Layout"
    panels:
      - type: "source"
        position: {row: 0, col: 0, width: 60, height: 30}
      
      - type: "registers"
        position: {row: 0, col: 60, width: 40, height: 15}
      
      - type: "console"
        position: {row: 15, col: 60, width: 40, height: 15}
  
  disasm_only:
    name: "Disassembly Focus"
    panels:
      - type: "disassembly"
        position: {row: 0, col: 0, width: 80, height: 35}
      
      - type: "registers"
        position: {row: 0, col: 80, width: 20, height: 35}

keybindings:
  global:
    "F5": "continue"
    "F10": "step_source"
    "F11": "step_instruction"
    "Ctrl+B": "toggle_breakpoint"
    "Alt+1": "switch_layout:debug_full"
    "Alt+2": "switch_layout:compact"
  
  source_panel:
    "g": "goto_line"
    "/": "search"
    "n": "next_match"

theme:
  name: "monokai"
  colors:
    current_line: "#3E3D32"
    breakpoint: "#F92672"
    highlight: "#FD971F"
```

### 2.2 Layout Manager Implementation

```python
class LayoutManager:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.current_layout = None
        self.panels = {}
    
    def load_config(self, path: str) -> Dict:
        """Load layout configuration from YAML/JSON"""
        with open(path) as f:
            return yaml.safe_load(f)
    
    def apply_layout(self, layout_name: str):
        """Apply specified layout"""
        layout = self.config['layouts'][layout_name]
        
        # Remove existing panels
        for panel in self.panels.values():
            panel.remove()
        self.panels.clear()
        
        # Create new panels
        for panel_spec in layout['panels']:
            panel = self.create_panel(panel_spec)
            self.panels[panel_spec['type']] = panel
        
        self.current_layout = layout_name
    
    def create_panel(self, spec: Dict) -> Widget:
        """Factory method to create panel from spec"""
        panel_type = spec['type']
        pos = spec['position']
        config = spec.get('config', {})
        
        if panel_type == 'source':
            return SourcePanel(pos, config)
        elif panel_type == 'registers':
            return RegistersPanel(pos, config)
        # ... other panel types
    
    def save_layout(self, layout_name: str):
        """Save current panel positions as new layout"""
        layout = {
            'name': layout_name,
            'panels': []
        }
        
        for panel_type, panel in self.panels.items():
            layout['panels'].append({
                'type': panel_type,
                'position': panel.get_position(),
                'config': panel.get_config()
            })
        
        self.config['layouts'][layout_name] = layout
        self.write_config()
```

### 2.3 Runtime Layout Adjustment

**Interactive Resize:**
- Drag panel borders to resize (if mouse supported)
- Keyboard shortcuts to adjust panel sizes
- Save current layout with custom name

**Preset Switching:**
- `Alt+1`, `Alt+2`, etc. to switch between predefined layouts
- Smooth transition with panel fade-in/fade-out

**Panel Show/Hide:**
- Toggle individual panels on/off
- Remaining panels expand to fill space
- Remember hidden panels for layout restore

## 3. Source Path Handling

### 3.1 Clang Path Behavior

**Clang Records:**
- Full absolute path to source file when compiled with `-g`
- Stores in `!DIFile(filename: "...", directory: "...")`
- Can be controlled with `-fdebug-prefix-map=OLD=NEW` flag

**Example:**
```bash
# Default: absolute paths
clang -g test.c -S -emit-llvm -o test.ll
# Result: !DIFile(filename: "test.c", directory: "/home/user/project")

# Remap paths for portability
clang -g test.c -fdebug-prefix-map=/home/user/project=. -S -emit-llvm -o test.ll
# Result: !DIFile(filename: "test.c", directory: ".")
```

### 3.2 Recommended Build Configuration

**Makefile:**
```makefile
# Project root
PROJECT_ROOT := $(shell pwd)

# Debug build with relative paths
CFLAGS_DEBUG := -g -fdebug-prefix-map=$(PROJECT_ROOT)=.

# Compilation
%.ll: %.c
	clang $(CFLAGS_DEBUG) -S -emit-llvm $< -o $@

%.asm: %.ll
	hsx-llc.py $< -o $@ --emit-debug $(basename $@).dbg

%.hxe: %.asm
	asm.py $< -o $(basename $@).hxo
	hld.py $(basename $@).hxo --debug-info $(basename $@).dbg --emit-sym $@.sym -o $@

# Generate source list for debugger
sources.json: $(SOURCES)
	@echo '{"sources": [' > $@
	@for src in $(SOURCES); do \
		echo "  {\"file\": \"$$src\", \"path\": \"$(PROJECT_ROOT)/$$src\"}," >> $@; \
	done
	@echo ']}' >> $@
```

### 3.3 Source List File Format

**Purpose:** Provide debugger with mapping from relative paths to absolute paths.

**Format (`sources.json`):**
```json
{
  "version": 1,
  "project_root": "/home/user/project",
  "sources": [
    {
      "file": "main.c",
      "path": "/home/user/project/main.c",
      "relative": "./main.c"
    },
    {
      "file": "utils/helper.c",
      "path": "/home/user/project/utils/helper.c",
      "relative": "./utils/helper.c"
    }
  ],
  "include_paths": [
    "/home/user/project/include",
    "/usr/local/include/hsx"
  ]
}
```

### 3.4 Path Resolution Algorithm

```python
class SourceResolver:
    def __init__(self, sources_json: Optional[str] = None):
        self.project_root = None
        self.source_map = {}
        self.search_paths = []
        
        if sources_json and os.path.exists(sources_json):
            self.load_sources_list(sources_json)
    
    def load_sources_list(self, path: str):
        """Load source list from JSON"""
        with open(path) as f:
            data = json.load(f)
        
        self.project_root = data.get('project_root')
        for src in data.get('sources', []):
            self.source_map[src['file']] = src['path']
        
        self.search_paths = data.get('include_paths', [])
    
    def resolve_source(self, sym_path: str) -> Optional[str]:
        """Resolve source file path from .sym file reference"""
        # Try exact match in source map
        if sym_path in self.source_map:
            return self.source_map[sym_path]
        
        # Try as absolute path
        if os.path.isabs(sym_path) and os.path.exists(sym_path):
            return sym_path
        
        # Try relative to project root
        if self.project_root:
            candidate = os.path.join(self.project_root, sym_path)
            if os.path.exists(candidate):
                return candidate
        
        # Try search paths
        for search_path in self.search_paths:
            candidate = os.path.join(search_path, sym_path)
            if os.path.exists(candidate):
                return candidate
        
        # Try relative to .sym file location
        sym_dir = os.path.dirname(self.sym_file_path)
        candidate = os.path.join(sym_dir, sym_path)
        if os.path.exists(candidate):
            return candidate
        
        return None
```

### 3.5 Build Script Integration

**Automatic Source List Generation:**
```python
#!/usr/bin/env python3
# build.py

import os
import json
from pathlib import Path

def generate_source_list(project_root: str, sources: List[str]) -> Dict:
    """Generate source list JSON"""
    data = {
        'version': 1,
        'project_root': str(Path(project_root).resolve()),
        'sources': []
    }
    
    for src in sources:
        src_path = Path(src)
        abs_path = (Path(project_root) / src_path).resolve()
        
        data['sources'].append({
            'file': str(src_path),
            'path': str(abs_path),
            'relative': f"./{src_path}"
        })
    
    return data

def main():
    # Discover all C files
    project_root = Path.cwd()
    sources = list(project_root.rglob('*.c'))
    
    # Generate source list
    source_list = generate_source_list(project_root, sources)
    
    # Write to build output
    with open('build/sources.json', 'w') as f:
        json.dump(source_list, f, indent=2)
    
    print(f"Generated source list with {len(sources)} files")

if __name__ == '__main__':
    main()
```

## 4. VS Code Debug Adapter Protocol Integration

### 4.1 Overview

**Debug Adapter Protocol (DAP):**
- Standard protocol between VS Code and debug backends
- JSON-RPC over stdin/stdout or TCP
- VS Code sends commands (launch, setBreakpoints, continue, step, etc.)
- Debug adapter responds with events (stopped, output, terminated, etc.)

**Benefits:**
- Use VS Code's built-in debugging UI
- Source-level debugging with rich features
- Breakpoint management in editor
- Variable inspection in hover tooltips
- Debug console integration

### 4.2 Architecture

```
┌────────────────┐         ┌──────────────────┐         ┌────────────────┐
│   VS Code      │  DAP    │  HSX Debug       │  RPC    │  HSX Executive │
│   Extension    │◄────────┤  Adapter         │◄────────┤  (execd.py)    │
│                │         │  (hsx-dap.py)    │         │                │
└────────────────┘         └──────────────────┘         └────────────────┘
        │                          │                            │
        │                          │                            │
    UI Layer              Protocol Translation          Runtime Control
```

**Components:**
1. **VS Code Extension:** Contributes debug configuration, launches adapter
2. **Debug Adapter:** Translates DAP ↔ HSX Executive RPC
3. **HSX Executive:** Existing debugger backend

### 4.3 Debug Adapter Implementation

**File: `python/hsx-dap.py`**

```python
#!/usr/bin/env python3
"""
HSX Debug Adapter for VS Code Debug Adapter Protocol
"""
import sys
import json
import logging
from typing import Dict, Any, Optional
import asyncio

from debugpy.adapter.protocol import DebugAdapter, DebugAdapterConnection
# Or use https://github.com/puremourning/vscode-debug-adapter-protocol

class HSXDebugAdapter(DebugAdapter):
    def __init__(self):
        super().__init__()
        self.executive_client = None  # Connection to execd.py
        self.session_id = None
        self.breakpoints = {}  # file:line -> addr mapping
        self.source_map = {}   # .sym file data
        self.stopped = False
    
    async def on_initialize(self, args: Dict) -> Dict:
        """Handle initialize request"""
        return {
            'supportsConfigurationDoneRequest': True,
            'supportsSetVariable': True,
            'supportsConditionalBreakpoints': False,
            'supportsHitConditionalBreakpoints': False,
            'supportsEvaluateForHovers': True,
            'supportsStepBack': False,
            'supportsRestartFrame': False,
            'supportsGotoTargetsRequest': False,
            'supportsStepInTargetsRequest': False,
            'supportsCompletionsRequest': False,
            'supportsExceptionOptions': False,
            'supportsValueFormattingOptions': True,
            'supportsDisassembleRequest': True,
            'supportsInstructionBreakpoints': True,
        }
    
    async def on_launch(self, args: Dict) -> None:
        """Handle launch request"""
        # Connect to executive
        host = args.get('host', 'localhost')
        port = args.get('port', 9998)
        self.executive_client = await self.connect_to_executive(host, port)
        
        # Open debug session
        response = await self.executive_client.request({
            'version': 1,
            'cmd': 'session.open',
            'client': 'vscode-dap',
            'capabilities': {
                'features': ['events', 'stack', 'watch', 'breakpoints']
            }
        })
        self.session_id = response['session_id']
        
        # Load program
        program = args['program']
        response = await self.executive_client.request({
            'version': 1,
            'cmd': 'load',
            'path': program
        })
        self.pid = response['image']['pid']
        
        # Load .sym file
        sym_file = program.replace('.hxe', '.sym')
        self.load_symbol_file(sym_file)
        
        # Subscribe to events
        await self.executive_client.request({
            'version': 1,
            'cmd': 'events.subscribe',
            'session': self.session_id,
            'filters': {
                'pid': [self.pid],
                'categories': ['debug_break', 'trace_step', 'stdout', 'stderr']
            }
        })
        
        # Start event loop
        asyncio.create_task(self.event_loop())
        
        # Send initialized event
        self.send_event('initialized', {})
    
    async def on_setBreakpoints(self, args: Dict) -> Dict:
        """Handle setBreakpoints request"""
        source = args['source']
        file_path = source['path']
        breakpoints = args.get('breakpoints', [])
        
        result_bps = []
        
        for bp in breakpoints:
            line = bp['line']
            
            # Resolve line to address using .sym file
            addr = self.resolve_line_to_addr(file_path, line)
            
            if addr:
                # Set breakpoint in executive
                response = await self.executive_client.request({
                    'version': 1,
                    'cmd': 'bp.set',
                    'session': self.session_id,
                    'pid': self.pid,
                    'addr': addr
                })
                
                result_bps.append({
                    'verified': True,
                    'line': line,
                    'id': response['breakpoint_id']
                })
                
                self.breakpoints[f"{file_path}:{line}"] = addr
            else:
                result_bps.append({
                    'verified': False,
                    'line': line,
                    'message': 'Could not resolve source line to address'
                })
        
        return {'breakpoints': result_bps}
    
    async def on_continue(self, args: Dict) -> Dict:
        """Handle continue request"""
        response = await self.executive_client.request({
            'version': 1,
            'cmd': 'continue',
            'session': self.session_id,
            'pid': self.pid
        })
        
        self.stopped = False
        return {'allThreadsContinued': True}
    
    async def on_next(self, args: Dict) -> None:
        """Handle next (step over) request"""
        # Step until we reach next source line
        current_line = self.get_current_line()
        
        while True:
            await self.executive_client.request({
                'version': 1,
                'cmd': 'step',
                'session': self.session_id,
                'pid': self.pid,
                'count': 1
            })
            
            new_line = self.get_current_line()
            if new_line != current_line:
                break
        
        self.stopped = True
        self.send_event('stopped', {
            'reason': 'step',
            'threadId': self.pid
        })
    
    async def on_stackTrace(self, args: Dict) -> Dict:
        """Handle stackTrace request"""
        response = await self.executive_client.request({
            'version': 1,
            'cmd': 'stack.info',
            'session': self.session_id,
            'pid': self.pid,
            'max_frames': 20
        })
        
        frames = []
        for frame in response['frames']:
            source_info = self.lookup_source_from_pc(frame['pc'])
            
            stack_frame = {
                'id': frame['depth'],
                'name': frame.get('symbol', f"0x{frame['pc']:04X}"),
                'line': source_info.get('line', 0),
                'column': 0,
            }
            
            if source_info:
                stack_frame['source'] = {
                    'name': os.path.basename(source_info['file']),
                    'path': source_info['file']
                }
            
            frames.append(stack_frame)
        
        return {'stackFrames': frames}
    
    async def on_scopes(self, args: Dict) -> Dict:
        """Handle scopes request"""
        return {
            'scopes': [
                {
                    'name': 'Registers',
                    'variablesReference': 1000,
                    'expensive': False
                },
                {
                    'name': 'Locals',
                    'variablesReference': 2000,
                    'expensive': False
                }
            ]
        }
    
    async def on_variables(self, args: Dict) -> Dict:
        """Handle variables request"""
        ref = args['variablesReference']
        
        if ref == 1000:  # Registers
            response = await self.executive_client.request({
                'version': 1,
                'cmd': 'reg.get',
                'session': self.session_id,
                'pid': self.pid
            })
            
            variables = []
            for name, value in response['registers'].items():
                variables.append({
                    'name': name,
                    'value': f"0x{value:04X}",
                    'variablesReference': 0
                })
            
            return {'variables': variables}
        
        elif ref == 2000:  # Locals (from watch list or stack)
            # TODO: Implement local variable display
            return {'variables': []}
    
    async def event_loop(self):
        """Process events from executive"""
        while True:
            event = await self.executive_client.receive_event()
            
            if event['type'] == 'debug_break':
                self.stopped = True
                self.send_event('stopped', {
                    'reason': 'breakpoint',
                    'threadId': self.pid,
                    'allThreadsStopped': True
                })
            
            elif event['type'] == 'stdout':
                self.send_event('output', {
                    'category': 'stdout',
                    'output': event['data']['text']
                })
            
            elif event['type'] == 'stderr':
                self.send_event('output', {
                    'category': 'stderr',
                    'output': event['data']['text']
                })
    
    def load_symbol_file(self, path: str):
        """Load .sym file for source mapping"""
        with open(path) as f:
            self.source_map = json.load(f)
    
    def resolve_line_to_addr(self, file: str, line: int) -> Optional[int]:
        """Find address for source file:line"""
        for inst in self.source_map.get('instructions', []):
            if inst.get('file') == file and inst.get('line') == line:
                return inst['pc']
        return None
    
    def lookup_source_from_pc(self, pc: int) -> Optional[Dict]:
        """Find source location for PC"""
        for inst in self.source_map.get('instructions', []):
            if inst['pc'] == pc:
                return {
                    'file': inst.get('file'),
                    'line': inst.get('line')
                }
        return None
    
    def get_current_line(self) -> Optional[int]:
        """Get current source line"""
        # Query PC from executive
        # Look up in .sym
        pass

def main():
    logging.basicConfig(level=logging.DEBUG)
    adapter = HSXDebugAdapter()
    adapter.run()

if __name__ == '__main__':
    main()
```

### 4.4 VS Code Extension

**Directory Structure:**
```
vscode-hsx/
├── package.json
├── src/
│   └── extension.ts
├── debugAdapter/
│   └── hsx-dap.py
└── README.md
```

**package.json:**
```json
{
  "name": "hsx-debug",
  "displayName": "HSX Debugger",
  "version": "0.1.0",
  "publisher": "hsx",
  "description": "Debug HSX applications",
  "categories": ["Debuggers"],
  "engines": {
    "vscode": "^1.70.0"
  },
  "activationEvents": ["onDebug"],
  "main": "./out/extension.js",
  "contributes": {
    "debuggers": [
      {
        "type": "hsx",
        "label": "HSX Debugger",
        "program": "./debugAdapter/hsx-dap.py",
        "runtime": "python3",
        "configurationAttributes": {
          "launch": {
            "required": ["program"],
            "properties": {
              "program": {
                "type": "string",
                "description": "Path to HXE executable",
                "default": "${workspaceFolder}/build/app.hxe"
              },
              "host": {
                "type": "string",
                "description": "Executive host",
                "default": "localhost"
              },
              "port": {
                "type": "number",
                "description": "Executive port",
                "default": 9998
              },
              "stopOnEntry": {
                "type": "boolean",
                "description": "Stop at entry point",
                "default": true
              }
            }
          }
        },
        "initialConfigurations": [
          {
            "type": "hsx",
            "request": "launch",
            "name": "Debug HSX Application",
            "program": "${workspaceFolder}/build/app.hxe",
            "host": "localhost",
            "port": 9998,
            "stopOnEntry": true
          }
        ]
      }
    ],
    "breakpoints": [
      {
        "language": "c"
      },
      {
        "language": "cpp"
      }
    ]
  }
}
```

**Usage:**
1. Install extension in VS Code
2. Open HSX project
3. Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "hsx",
      "request": "launch",
      "name": "Debug HSX App",
      "program": "${workspaceFolder}/build/app.hxe"
    }
  ]
}
```
4. Press F5 to start debugging
5. Set breakpoints in C source files
6. Step through code, inspect variables

### 4.5 Implementation Effort Estimate

**Low Effort (1-2 weeks):**
- Basic debug adapter with launch/continue/step/breakpoints
- Stack traces and register display
- Uses existing HSX executive RPC

**Medium Effort (3-4 weeks):**
- Add variable inspection and hover evaluation
- Implement watch expressions
- Memory viewer integration

**High Effort (6-8 weeks):**
- Full DAP feature parity
- Expression evaluation
- Conditional breakpoints
- Hot reload support
- Multi-process debugging

**Critical Dependencies:**
- .sym file with complete line mapping (Phase 2 debug metadata)
- Executive implements all required RPCs (already planned)
- Python DAP library (several available: debugpy, ptvsd, vscode-debugprotocol)

### 4.6 Alternative: Language Server Protocol (LSP)

For code intelligence without debugging, consider HSX Language Server:
- Syntax highlighting
- Go to definition (using .sym files)
- Hover information
- Code completion for HSX APIs
- Diagnostic messages from compiler

**Less effort than DAP, valuable standalone feature.**

## 5. Implementation Priority

**Phase 1 (Essential):**
1. Source panel in TUI with basic display
2. Path resolution with relative paths
3. Build script generates relative paths

**Phase 2 (Enhanced):**
1. Configurable TUI layouts (YAML config)
2. Source file caching and search paths
3. Syntax highlighting

**Phase 3 (Advanced):**
1. VS Code Debug Adapter (basic)
2. Source list generation in build
3. Runtime layout adjustment

**Phase 4 (Full Featured):**
1. Complete DAP implementation
2. VS Code extension polish
3. Expression evaluation

## 6. Summary

**Can we show source files in TUI?**
Yes. Add source panel that loads files using PC→line mapping from .sym.

**Configurable window layouts?**
Yes. YAML/JSON config file specifying panel types, positions, and settings. Runtime loading and switching.

**Does Clang preserve paths?**
Yes. Use `-fdebug-prefix-map=/abs/path=.` for relative paths. Build script can generate source list JSON mapping files to absolute paths.

**VS Code integration feasible?**
Yes. Implement Debug Adapter Protocol (DAP) translator between VS Code and HSX executive. Moderate effort (3-4 weeks for basic functionality). Reuses all existing executive RPC infrastructure.

**Next Steps:**
1. Update 04.10--TUI_Debugger.md with source panel design
2. Create TUI layout configuration specification
3. Document build system path handling
4. Create VS Code DAP adapter prototype
