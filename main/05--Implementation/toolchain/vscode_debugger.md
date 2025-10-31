# VS Code Debugger Integration Implementation Plan

## Overview
This document specifies the implementation of the HSX Debug Adapter Protocol (DAP) integration for Visual Studio Code, enabling full-featured debugging of HSX applications directly within VS Code's UI.

## Design References
- Design: [TUI-SourceDisplay-VSCode.md](../../04--Design/TUI-SourceDisplay-VSCode.md) Section 4
- Design: [04.09--Debugger.md](../../04--Design/04.09--Debugger.md)
- Design: [04.02--Executive.md](../../04--Design/04.02--Executive.md) Sections 5.3-5.7
- Spec: [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/)

## Architecture

```
┌──────────────────────┐
│   VS Code Editor     │
│   - Source Display   │
│   - Breakpoint UI    │
│   - Variable View    │
│   - Debug Console    │
└──────────┬───────────┘
           │ Debug Adapter Protocol (JSON-RPC)
           │ stdio or TCP
┌──────────▼───────────┐
│   hsx-dap.py         │
│   Debug Adapter      │
│   - Protocol Trans   │
│   - State Mgmt       │
│   - Symbol Lookup    │
└──────────┬───────────┘
           │ Executive RPC (JSON/TCP)
           │ port 9998
┌──────────▼───────────┐
│   HSX Executive      │
│   (execd.py)         │
│   - VM Control       │
│   - Event Stream     │
│   - Breakpoints      │
└──────────────────────┘
```

## Implementation Phases

### Phase 1: Core Debug Adapter (Week 1-2)
**Goal:** Basic debugging functionality - launch, breakpoints, stepping, stack traces

**Deliverables:**
1. `python/hsx-dap.py` - Debug adapter server
2. VS Code extension skeleton
3. Basic protocol handlers
4. Symbol file loading

**Features:**
- Launch configuration
- Continue/Pause/Stop
- Step Over/Into/Out
- Set/Clear breakpoints
- Stack trace display
- Register inspection

### Phase 2: Enhanced Features (Week 3-4)
**Goal:** Variable inspection, hover evaluation, improved UX

**Deliverables:**
1. Variable scopes (Registers, Locals, Globals)
2. Hover evaluation
3. Watch expressions
4. Memory viewer integration
5. Output redirection (stdout/stderr)

### Phase 3: Advanced Features (Week 5-6)
**Goal:** Polish and production readiness

**Deliverables:**
1. Conditional breakpoints
2. Hit count breakpoints
3. Logpoints (breakpoints that log without stopping)
4. Multi-process debugging
5. Exception handling
6. Performance optimization

### Phase 4: Distribution (Week 7-8)
**Goal:** Package and publish extension

**Deliverables:**
1. Extension marketplace preparation
2. Documentation and tutorials
3. Sample projects
4. CI/CD integration
5. User testing and feedback

## File Structure

```
vscode-hsx/
├── package.json                 # Extension manifest
├── README.md                    # User documentation
├── CHANGELOG.md                 # Version history
├── .vscodeignore               # Files to exclude from package
├── src/
│   └── extension.ts            # Extension activation logic
├── debugAdapter/
│   ├── hsx-dap.py              # Debug adapter implementation
│   ├── protocol.py             # DAP protocol definitions
│   ├── executive_client.py     # Executive RPC client
│   └── symbol_loader.py        # Symbol file (.sym) handling
├── syntaxes/
│   └── mvasm.tmLanguage.json   # MVASM syntax highlighting
├── snippets/
│   └── mvasm.json              # Code snippets
├── examples/
│   ├── hello/
│   │   ├── hello.c
│   │   ├── Makefile
│   │   └── .vscode/
│   │       └── launch.json
│   └── mailbox/
│       ├── producer.c
│       ├── consumer.c
│       ├── Makefile
│       └── .vscode/
│           └── launch.json
└── test/
    ├── suite/
    │   └── extension.test.ts
    └── adapter/
        └── test_dap.py
```

## Debug Adapter Implementation

### File: `debugAdapter/hsx-dap.py`

```python
#!/usr/bin/env python3
"""
HSX Debug Adapter for Visual Studio Code
Implements Debug Adapter Protocol (DAP) for HSX debugging
"""

import sys
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

# Simple DAP protocol handler (can use library like debugpy or implement directly)
class DAPProtocol:
    """Handle DAP JSON-RPC protocol over stdin/stdout"""
    
    def __init__(self):
        self.seq = 1
        self.handlers = {}
    
    def send_event(self, event: str, body: Dict = None):
        """Send DAP event to VS Code"""
        msg = {
            'seq': self.seq,
            'type': 'event',
            'event': event,
            'body': body or {}
        }
        self.seq += 1
        self._send_message(msg)
    
    def send_response(self, request_seq: int, command: str, 
                     success: bool = True, body: Dict = None, message: str = None):
        """Send DAP response to VS Code"""
        msg = {
            'seq': self.seq,
            'type': 'response',
            'request_seq': request_seq,
            'command': command,
            'success': success,
            'body': body or {}
        }
        if message:
            msg['message'] = message
        self.seq += 1
        self._send_message(msg)
    
    def _send_message(self, msg: Dict):
        """Send JSON message with Content-Length header"""
        content = json.dumps(msg)
        header = f'Content-Length: {len(content)}\r\n\r\n'
        sys.stdout.write(header + content)
        sys.stdout.flush()
    
    async def read_message(self) -> Optional[Dict]:
        """Read DAP message from stdin"""
        # Read Content-Length header
        line = sys.stdin.readline()
        if not line:
            return None
        
        if not line.startswith('Content-Length:'):
            return None
        
        length = int(line.split(':')[1].strip())
        
        # Skip blank line
        sys.stdin.readline()
        
        # Read content
        content = sys.stdin.read(length)
        return json.loads(content)


class ExecutiveClient:
    """Client for HSX Executive RPC"""
    
    def __init__(self, host: str = 'localhost', port: int = 9998):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.event_queue = asyncio.Queue()
    
    async def connect(self):
        """Connect to executive"""
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port
        )
        # Start event listener
        asyncio.create_task(self._event_loop())
    
    async def request(self, cmd: Dict) -> Dict:
        """Send RPC request and wait for response"""
        msg = json.dumps(cmd) + '\n'
        self.writer.write(msg.encode())
        await self.writer.drain()
        
        # Read response
        line = await self.reader.readline()
        return json.loads(line)
    
    async def _event_loop(self):
        """Read events from executive and queue them"""
        while True:
            line = await self.reader.readline()
            if not line:
                break
            
            event = json.loads(line)
            if 'seq' in event:  # It's an event
                await self.event_queue.put(event)
    
    async def next_event(self) -> Dict:
        """Get next event from queue"""
        return await self.event_queue.get()


class SymbolLoader:
    """Load and query .sym files"""
    
    def __init__(self, sym_path: str):
        with open(sym_path) as f:
            self.data = json.load(f)
        
        # Build lookup indices
        self._build_indices()
    
    def _build_indices(self):
        """Build fast lookup structures"""
        self.pc_to_line = {}
        for inst in self.data.get('instructions', []):
            if 'file' in inst and 'line' in inst:
                self.pc_to_line[inst['pc']] = {
                    'file': inst['file'],
                    'line': inst['line'],
                    'column': inst.get('column', 0)
                }
        
        self.line_to_pc = {}
        for inst in self.data.get('instructions', []):
            if 'file' in inst and 'line' in inst:
                key = (inst['file'], inst['line'])
                if key not in self.line_to_pc:
                    self.line_to_pc[key] = inst['pc']
        
        self.functions = {
            f['name']: f for f in self.data['symbols'].get('functions', [])
        }
    
    def resolve_line(self, file: str, line: int) -> Optional[int]:
        """Find PC for source file:line"""
        return self.line_to_pc.get((file, line))
    
    def resolve_pc(self, pc: int) -> Optional[Dict]:
        """Find source location for PC"""
        return self.pc_to_line.get(pc)
    
    def get_function(self, name: str) -> Optional[Dict]:
        """Get function info by name"""
        return self.functions.get(name)


class HSXDebugAdapter:
    """Main debug adapter class"""
    
    def __init__(self):
        self.protocol = DAPProtocol()
        self.executive = None
        self.symbol_loader = None
        self.session_id = None
        self.pid = None
        self.breakpoints = {}  # (file, line) -> bp_id
        self.stopped = False
        self.stop_reason = None
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register DAP request handlers"""
        self.handlers = {
            'initialize': self.handle_initialize,
            'launch': self.handle_launch,
            'attach': self.handle_attach,
            'setBreakpoints': self.handle_set_breakpoints,
            'setExceptionBreakpoints': self.handle_set_exception_breakpoints,
            'configurationDone': self.handle_configuration_done,
            'continue': self.handle_continue,
            'next': self.handle_next,
            'stepIn': self.handle_step_in,
            'stepOut': self.handle_step_out,
            'pause': self.handle_pause,
            'stackTrace': self.handle_stack_trace,
            'scopes': self.handle_scopes,
            'variables': self.handle_variables,
            'source': self.handle_source,
            'threads': self.handle_threads,
            'evaluate': self.handle_evaluate,
            'disconnect': self.handle_disconnect,
        }
    
    async def handle_initialize(self, req: Dict) -> Dict:
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
            'supportsReadMemoryRequest': True,
            'supportsWriteMemoryRequest': True,
        }
    
    async def handle_launch(self, req: Dict) -> None:
        """Handle launch request"""
        args = req['arguments']
        
        # Connect to executive
        host = args.get('host', 'localhost')
        port = args.get('port', 9998)
        
        self.executive = ExecutiveClient(host, port)
        await self.executive.connect()
        
        # Open debug session
        response = await self.executive.request({
            'version': 1,
            'cmd': 'session.open',
            'client': 'vscode-dap',
            'capabilities': {
                'features': ['events', 'stack', 'watch', 'breakpoints']
            }
        })
        self.session_id = response['session']['id']
        
        # Load program
        program = args['program']
        response = await self.executive.request({
            'version': 1,
            'cmd': 'load',
            'session': self.session_id,
            'path': program
        })
        self.pid = response['image']['pid']
        
        # Load symbol file
        sym_file = Path(program).with_suffix('.sym')
        if sym_file.exists():
            self.symbol_loader = SymbolLoader(str(sym_file))
        
        # Subscribe to events
        await self.executive.request({
            'version': 1,
            'cmd': 'events.subscribe',
            'session': self.session_id,
            'filters': {
                'pid': [self.pid],
                'categories': ['debug_break', 'trace_step', 'task_state', 
                              'stdout', 'stderr', 'watch_update']
            }
        })
        
        # Start event processing
        asyncio.create_task(self.process_events())
        
        # Send initialized event
        self.protocol.send_event('initialized')
        
        # Stop at entry if requested
        if args.get('stopOnEntry', True):
            self.stopped = True
            self.stop_reason = 'entry'
            self.protocol.send_event('stopped', {
                'reason': 'entry',
                'threadId': self.pid,
                'allThreadsStopped': True
            })
    
    async def handle_set_breakpoints(self, req: Dict) -> Dict:
        """Handle setBreakpoints request"""
        args = req['arguments']
        source = args['source']
        file_path = source['path']
        requested_bps = args.get('breakpoints', [])
        
        # Clear old breakpoints for this file
        old_bps = [(f, l) for (f, l) in self.breakpoints.keys() if f == file_path]
        for key in old_bps:
            bp_id = self.breakpoints[key]
            await self.executive.request({
                'version': 1,
                'cmd': 'bp.clear',
                'session': self.session_id,
                'pid': self.pid,
                'breakpoint_id': bp_id
            })
            del self.breakpoints[key]
        
        # Set new breakpoints
        result_bps = []
        for bp in requested_bps:
            line = bp['line']
            
            # Resolve line to address
            if self.symbol_loader:
                addr = self.symbol_loader.resolve_line(file_path, line)
            else:
                addr = None
            
            if addr is not None:
                # Set breakpoint in executive
                response = await self.executive.request({
                    'version': 1,
                    'cmd': 'bp.set',
                    'session': self.session_id,
                    'pid': self.pid,
                    'addr': addr
                })
                
                bp_id = response.get('breakpoint_id', addr)
                self.breakpoints[(file_path, line)] = bp_id
                
                result_bps.append({
                    'verified': True,
                    'line': line,
                    'id': bp_id
                })
            else:
                result_bps.append({
                    'verified': False,
                    'line': line,
                    'message': 'Could not resolve source line to address'
                })
        
        return {'breakpoints': result_bps}
    
    async def handle_continue(self, req: Dict) -> Dict:
        """Handle continue request"""
        await self.executive.request({
            'version': 1,
            'cmd': 'continue',
            'session': self.session_id,
            'pid': self.pid
        })
        
        self.stopped = False
        return {'allThreadsContinued': True}
    
    async def handle_next(self, req: Dict) -> None:
        """Handle next (step over) request"""
        # Get current source line
        pc_resp = await self.executive.request({
            'version': 1,
            'cmd': 'reg.get',
            'session': self.session_id,
            'pid': self.pid,
            'reg': 'PC'
        })
        current_pc = pc_resp['registers']['PC']
        
        if self.symbol_loader:
            current_line_info = self.symbol_loader.resolve_pc(current_pc)
            current_line = current_line_info['line'] if current_line_info else None
        else:
            current_line = None
        
        # Step until we reach next source line
        max_steps = 1000  # Safety limit
        for _ in range(max_steps):
            await self.executive.request({
                'version': 1,
                'cmd': 'step',
                'session': self.session_id,
                'pid': self.pid,
                'steps': 1
            })
            
            # Check new PC
            pc_resp = await self.executive.request({
                'version': 1,
                'cmd': 'reg.get',
                'session': self.session_id,
                'pid': self.pid,
                'reg': 'PC'
            })
            new_pc = pc_resp['registers']['PC']
            
            if self.symbol_loader:
                new_line_info = self.symbol_loader.resolve_pc(new_pc)
                new_line = new_line_info['line'] if new_line_info else None
                
                if new_line and new_line != current_line:
                    break
            else:
                # Without symbols, just step once
                break
        
        self.stopped = True
        self.stop_reason = 'step'
        self.protocol.send_event('stopped', {
            'reason': 'step',
            'threadId': self.pid,
            'allThreadsStopped': True
        })
    
    async def handle_stack_trace(self, req: Dict) -> Dict:
        """Handle stackTrace request"""
        response = await self.executive.request({
            'version': 1,
            'cmd': 'stack.info',
            'session': self.session_id,
            'pid': self.pid,
            'max_frames': 50
        })
        
        frames = []
        for frame in response['frames']:
            pc = frame['pc']
            
            # Look up source location
            if self.symbol_loader:
                source_info = self.symbol_loader.resolve_pc(pc)
            else:
                source_info = None
            
            stack_frame = {
                'id': frame['depth'],
                'name': frame.get('symbol', f"0x{pc:04X}"),
                'line': source_info['line'] if source_info else 0,
                'column': source_info.get('column', 0) if source_info else 0,
                'instructionPointerReference': hex(pc)
            }
            
            if source_info:
                import os
                stack_frame['source'] = {
                    'name': os.path.basename(source_info['file']),
                    'path': source_info['file']
                }
            
            frames.append(stack_frame)
        
        return {
            'stackFrames': frames,
            'totalFrames': len(frames)
        }
    
    async def handle_scopes(self, req: Dict) -> Dict:
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
    
    async def handle_variables(self, req: Dict) -> Dict:
        """Handle variables request"""
        ref = req['arguments']['variablesReference']
        
        if ref == 1000:  # Registers
            response = await self.executive.request({
                'version': 1,
                'cmd': 'reg.get',
                'session': self.session_id,
                'pid': self.pid
            })
            
            variables = []
            for name, value in response['registers'].items():
                variables.append({
                    'name': name,
                    'value': f"0x{value:04X}" if isinstance(value, int) else str(value),
                    'variablesReference': 0
                })
            
            return {'variables': variables}
        
        return {'variables': []}
    
    async def handle_threads(self, req: Dict) -> Dict:
        """Handle threads request"""
        return {
            'threads': [
                {
                    'id': self.pid,
                    'name': f"PID {self.pid}"
                }
            ]
        }
    
    async def process_events(self):
        """Process events from executive"""
        while True:
            try:
                event = await self.executive.next_event()
                
                if event['type'] == 'debug_break':
                    self.stopped = True
                    self.stop_reason = 'breakpoint'
                    self.protocol.send_event('stopped', {
                        'reason': 'breakpoint',
                        'threadId': self.pid,
                        'allThreadsStopped': True
                    })
                
                elif event['type'] == 'stdout':
                    self.protocol.send_event('output', {
                        'category': 'stdout',
                        'output': event['data']['text']
                    })
                
                elif event['type'] == 'stderr':
                    self.protocol.send_event('output', {
                        'category': 'stderr',
                        'output': event['data']['text']
                    })
                
                elif event['type'] == 'task_state':
                    if event['data']['new_state'] == 'terminated':
                        self.protocol.send_event('exited', {
                            'exitCode': 0
                        })
                        self.protocol.send_event('terminated')
            
            except Exception as e:
                logging.error(f"Error processing event: {e}")
    
    async def run(self):
        """Main message loop"""
        while True:
            msg = await self.protocol.read_message()
            if not msg:
                break
            
            if msg['type'] == 'request':
                command = msg['command']
                handler = self.handlers.get(command)
                
                if handler:
                    try:
                        result = await handler(msg)
                        self.protocol.send_response(
                            msg['seq'], command, True, result
                        )
                    except Exception as e:
                        logging.error(f"Error handling {command}: {e}")
                        self.protocol.send_response(
                            msg['seq'], command, False, 
                            message=str(e)
                        )
                else:
                    self.protocol.send_response(
                        msg['seq'], command, False,
                        message=f"Unknown command: {command}"
                    )


async def main():
    logging.basicConfig(
        filename='/tmp/hsx-dap.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    adapter = HSXDebugAdapter()
    await adapter.run()


if __name__ == '__main__':
    asyncio.run(main())
```

## VS Code Extension

### File: `package.json`

```json
{
  "name": "hsx-debug",
  "displayName": "HSX Debugger",
  "version": "0.1.0",
  "publisher": "hsx",
  "description": "Debug HSX applications with full source-level support",
  "categories": ["Debuggers"],
  "keywords": ["hsx", "debug", "embedded", "vm"],
  "engines": {
    "vscode": "^1.70.0"
  },
  "activationEvents": [
    "onDebug",
    "onLanguage:c",
    "onLanguage:cpp"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "languages": [{
      "id": "mvasm",
      "aliases": ["MVASM", "mvasm"],
      "extensions": [".mvasm", ".asm"],
      "configuration": "./language-configuration.json"
    }],
    "grammars": [{
      "language": "mvasm",
      "scopeName": "source.mvasm",
      "path": "./syntaxes/mvasm.tmLanguage.json"
    }],
    "debuggers": [{
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
              "default": "${workspaceFolder}/build/debug/app.hxe"
            },
            "host": {
              "type": "string",
              "description": "Executive host address",
              "default": "localhost"
            },
            "port": {
              "type": "number",
              "description": "Executive TCP port",
              "default": 9998
            },
            "stopOnEntry": {
              "type": "boolean",
              "description": "Automatically stop after launch",
              "default": true
            },
            "cwd": {
              "type": "string",
              "description": "Working directory",
              "default": "${workspaceFolder}"
            }
          }
        }
      },
      "initialConfigurations": [
        {
          "type": "hsx",
          "request": "launch",
          "name": "Debug HSX Application",
          "program": "${workspaceFolder}/build/debug/app.hxe",
          "stopOnEntry": true
        }
      ],
      "configurationSnippets": [
        {
          "label": "HSX: Launch",
          "description": "Launch and debug HSX application",
          "body": {
            "type": "hsx",
            "request": "launch",
            "name": "Debug HSX App",
            "program": "^\"\\${workspaceFolder}/build/debug/app.hxe\""
          }
        }
      ]
    }],
    "breakpoints": [
      { "language": "c" },
      { "language": "cpp" }
    ]
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./",
    "package": "vsce package"
  },
  "devDependencies": {
    "@types/node": "^16.x",
    "@types/vscode": "^1.70.0",
    "typescript": "^4.9.0",
    "@vscode/vsce": "^2.15.0"
  }
}
```

### File: `src/extension.ts`

```typescript
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    console.log('HSX Debug extension activated');
    
    // Register configuration provider
    context.subscriptions.push(
        vscode.debug.registerDebugConfigurationProvider('hsx', new HSXConfigurationProvider())
    );
}

export function deactivate() {
    console.log('HSX Debug extension deactivated');
}

class HSXConfigurationProvider implements vscode.DebugConfigurationProvider {
    resolveDebugConfiguration(
        folder: vscode.WorkspaceFolder | undefined,
        config: vscode.DebugConfiguration,
        token?: vscode.CancellationToken
    ): vscode.ProviderResult<vscode.DebugConfiguration> {
        
        // If launch.json is missing, provide defaults
        if (!config.type && !config.request && !config.name) {
            const editor = vscode.window.activeTextEditor;
            if (editor && (editor.document.languageId === 'c' || editor.document.languageId === 'cpp')) {
                config.type = 'hsx';
                config.name = 'Launch';
                config.request = 'launch';
                config.program = '${workspaceFolder}/build/debug/app.hxe';
                config.stopOnEntry = true;
            }
        }
        
        if (!config.program) {
            return vscode.window.showInformationMessage(
                "Cannot find a program to debug"
            ).then(_ => {
                return undefined;
            });
        }
        
        return config;
    }
}
```

## Testing Strategy

### Unit Tests
```python
# test/adapter/test_dap.py
import pytest
import asyncio
from debugAdapter.hsx_dap import HSXDebugAdapter, SymbolLoader

def test_symbol_loader():
    """Test symbol file loading"""
    loader = SymbolLoader('test/fixtures/test.sym')
    
    # Test line resolution
    addr = loader.resolve_line('main.c', 10)
    assert addr == 0x0100
    
    # Test PC resolution
    loc = loader.resolve_pc(0x0100)
    assert loc['file'] == 'main.c'
    assert loc['line'] == 10

@pytest.mark.asyncio
async def test_debug_adapter_initialize():
    """Test DAP initialize"""
    adapter = HSXDebugAdapter()
    result = await adapter.handle_initialize({})
    
    assert result['supportsConfigurationDoneRequest'] is True
    assert result['supportsConditionalBreakpoints'] is False
```

### Integration Tests
1. Launch test application
2. Set breakpoint
3. Continue execution
4. Verify stop at breakpoint
5. Step through code
6. Inspect variables
7. Evaluate expressions
8. Terminate session

### Manual Testing Checklist
- [ ] Extension loads in VS Code
- [ ] Debug configuration appears
- [ ] Can launch debug session
- [ ] Breakpoints set correctly
- [ ] Can step through code
- [ ] Stack trace displays
- [ ] Variables show in debug view
- [ ] Output appears in debug console
- [ ] Can pause/continue execution
- [ ] Session terminates cleanly

## Build and Installation

### Development Setup
```bash
# Clone repository
git clone https://github.com/hsx/vscode-hsx
cd vscode-hsx

# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Open in VS Code
code .

# Press F5 to launch Extension Development Host
```

### Package Extension
```bash
# Install vsce
npm install -g @vscode/vsce

# Package extension
vsce package

# This creates hsx-debug-0.1.0.vsix
```

### Install Packaged Extension
```bash
# Install from VSIX
code --install-extension hsx-debug-0.1.0.vsix

# Or install via VS Code UI:
# Extensions > ... > Install from VSIX
```

## Usage

### 1. Create Launch Configuration
`.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "hsx",
      "request": "launch",
      "name": "Debug HSX App",
      "program": "${workspaceFolder}/build/debug/app.hxe",
      "preLaunchTask": "build-debug",
      "stopOnEntry": true
    }
  ]
}
```

### 2. Create Build Task
`.vscode/tasks.json`:
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "build-debug",
      "type": "shell",
      "command": "python3",
      "args": [
        "python/hsx-cc-build.py",
        "-C", "${workspaceFolder}",
        "--debug"
      ],
      "group": {
        "kind": "build",
        "isDefault": true
      }
    }
  ]
}
```

### 3. Debug Workflow
1. Open C/C++ source file
2. Click in gutter to set breakpoint
3. Press F5 to start debugging
4. Use debug toolbar or keyboard shortcuts:
   - F5: Continue
   - F10: Step Over
   - F11: Step Into
   - Shift+F11: Step Out
   - F9: Toggle Breakpoint
   - Ctrl+Shift+F5: Restart
   - Shift+F5: Stop

## Distribution

### Marketplace Publishing
```bash
# Login to publisher account
vsce login hsx

# Publish to marketplace
vsce publish

# Or publish specific version
vsce publish 0.1.0
```

### Documentation Requirements
- README with installation and usage
- CHANGELOG with version history
- Screenshots of debugging in action
- Sample projects
- Troubleshooting guide

## Success Criteria
- [ ] Extension installs without errors
- [ ] Can debug simple Hello World program
- [ ] Breakpoints work reliably
- [ ] Source-level stepping matches C code
- [ ] Stack traces show function names and line numbers
- [ ] Register and variable inspection works
- [ ] Debug console shows program output
- [ ] Extension handles edge cases gracefully
- [ ] Documentation is clear and complete
- [ ] Published to marketplace with 4+ star rating

## Timeline and Milestones

**Week 1-2: Core Adapter**
- Milestone: Basic debugging works (launch, break, step, continue)
- Demo: Debug simple program with breakpoints

**Week 3-4: Enhanced Features**
- Milestone: Variable inspection and watches work
- Demo: Inspect variables and watch expressions

**Week 5-6: Polish**
- Milestone: All major features implemented
- Demo: Debug complex multi-file program

**Week 7-8: Release**
- Milestone: Extension published to marketplace
- Demo: Public announcement and tutorial video

## Dependencies and Prerequisites

**Required:**
- HSX Executive implementing all debug RPC APIs
- Symbol files (.sym) with line number information
- Python 3.9+ for debug adapter
- Node.js 16+ for extension build
- VS Code 1.70+

**Optional:**
- sources.json for path mapping
- Build integration with hsx-cc-build.py
- MVASM syntax highlighting

## Future Enhancements

**Phase 5+:**
- Reverse debugging (step backwards)
- Time-travel debugging with execution replay
- Remote debugging over network
- Multi-threaded/multi-process support
- Integration with VS Code Testing API
- Code coverage visualization
- Performance profiling integration
- Language Server Protocol (LSP) for code intelligence
