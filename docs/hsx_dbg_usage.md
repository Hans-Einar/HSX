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
