Blinkenlights Control Panel
===========================

This concept sketches a pygame-based “front panel” for HSX development. The UI mimics vintage blinkenlight consoles where each running HSX task occupies a slot with live state indicators and manual controls.

High-Level Idea
---------------

- Run alongside the HSX executive, invoking `python/shell_client.py` RPC commands to inspect (`dumpregs`, `peek`) and manipulate (`poke`, `pause`, `resume`, `kill`) tasks.
- Main left sidebar hosts global machine controls: attach/detach, start/stop auto-stepping, single-step, halt, load image.
- Right-hand side lists scrollable task slots; each slot shows register lights, memory viewers, and per-task controls.
- Interact with register lights by clicking: highlight (e.g., green ring) to toggle bits or choose a register via selector wheel; commit changes with `poke`.
- Optional flip/flop switches emulate PDP-11 front panels for playful bit editing when space allows.

TODO
----

- [x] Prototype pygame front panel (`python/blinkenlights.py`) with task list and pause/resume/kill buttons.
- [ ] Define pygame window layout: sidebar dimensions, slot size, scroll behaviour.
- [x] Wrap shell_client RPCs so the panel can issue commands without spawning subprocesses each time.
- [x] Implement global controls: halt, single-step, run, attach/detach, load file dialog.
- [ ] Render task slots with live register blinkenlights and per-slot pause/resume/kill buttons.
- [ ] Add register selector/animation and memory watch region with editable cells.
- [x] Support loading programs into slots via browse dialog and associate metadata with task IDs.
- [ ] Integrate status polling (e.g., periodic `dumpregs`/`info`) with throttling to avoid saturating the executive.
- [ ] Provide visual feedback for paused vs running vs terminated tasks.
- [ ] Document usage and troubleshooting once prototype is stable.

Prototype Usage
---------------

- Install pygame (`pip install pygame`).
- Launch the panel with `python python/blinkenlights.py --host 127.0.0.1 --port 9998` while the executive daemon is running (it will attempt an `attach` automatically).
- Sidebar buttons: Attach/Detach, Load (Tk file dialog), Refresh, Start/Stop Auto, Step 100.
- Per-task buttons issue pause/resume/kill RPCs; register rows reflect `dumpregs` snapshots.
