# hsx-dbg CLI Usage

## Overview

`hsx-dbg` is the dedicated CLI debugger described in main/04--Design/04.09--Debugger.md.
Launch it interactively:

```
python/python3 python/hsx_dbg.py --host 127.0.0.1 --port 9998
```

Or run single commands:

```
python python/hsx_dbg.py --json --command "ps"
```

## JSON Output

When `--json` is set, every command outputs a consistent schema:

```
{"status": "ok", "result": {...}}
```

Errors use `{"status": "error", "error": "message", "details": {...}}`.

## Multiline Commands

End a line with `\` to continue typing on the next line:

```
hsxdbg> break main \
> loop
```

## Aliases

Use `alias foo bar` to map `foo` to command `bar`. `alias` with no arguments lists
current aliases. `alias --clear` removes all mappings.

## Session Management & Observer Mode

Use `session info` / `session list` to inspect sessions, `attach` / `detach` to
take control, and `status` to verify the current connection. `observer on`
switches the CLI into read-only mode (no attach/pause/step), while `observer off`
re-enables control commands.

### Keepalive Options

`--keepalive-interval <seconds>` overrides the heartbeat used for automatic
`session.keepalive` pings. `--no-keepalive` disables those pings entirely (useful
when the executive runs on localhost and sessions are short-lived).

## JSON Fields

Task listings include:

- `app_name`
- Metadata counts (`values`, `commands`, `mailboxes`)
- Trace state and steps

Register dumps include `selected_registers` when the executive provides them.

## Breakpoints

`break add <pid> <spec>` accepts raw addresses (`0x1234`), symbol names (requires
`--symbols` or `symbols <path>`), or `file.c:42` source locations. Use `break list`
to show active and locally disabled breakpoints, `break disable`/`break enable`
to toggle without losing context, and `break clearall` to remove everything for a PID.

## Watches

`watch add <pid> <expr>` registers a memory or local watch (the executive evaluates
the expression). `watch remove` and `watch list` manage existing watches. Watch
updates arrive via the event stream when expressions change.

## Symbol Files

Provide a .sym path via `--symbols /path/to/app.sym` or the `symbols <path>`
command. This enables `break` to resolve symbols (`main`) and `file.c:line`
specifications.

## Stack Navigation

`stack bt <pid>` fetches a backtrace and caches frames locally. Use `stack frame <pid> <n>`
to select a specific frame, `stack up <pid>` / `stack down <pid>` to move between frames,
and note that the CLI highlights the currently selected frame in `stack bt` output.

## Memory Inspection

`mem read <pid> <address>` mirrors the classic `x/<fmt>` syntax. Choose formats with
`--format x|d|i|s` and widths via `--width`. `mem dump <pid> <start> <end>` produces a
16-byte-per-row hex dump that always includes an ASCII gutter, making it easier to detect
string fragments or padding bytes. The CLI also understands the executive's `memory regions`
metadata so you can quickly list mapped ranges with `mem regions <pid>`.

## Disassembly

`disasm <pid> [symbol|address]` streams instructions with function annotations and source
locations (when the executive provides them). The arrow prefix (`=>`) marks the current PC
and offsets appear as `<function+0xN>` to match the design document. Add `--source` to force
source lookups even when symbol data is sparse.
