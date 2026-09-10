# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`meshcore-cli` is a Python CLI/interactive shell for talking to MeshCore companion radios (mesh LoRa nodes) over BLE, TCP, or Serial. It wraps the [`meshcore`](https://github.com/fdlamotte/meshcore_py) Python library. Installed entry points are `meshcli` and `meshcore-cli`, both pointing to `meshcore_cli.meshcore_cli:cli`.

## Development commands

There is no test suite, linter, or CI configured in this repo — don't invent commands for them.

Install/run locally:
```
pip install -e .
meshcli <args> <commands>
```

Build (hatchling backend):
```
python -m build
```

Nix (flake provides a `meshcore-cli` package, pinned against a specific `meshcore` PyPI version in `flake.nix`):
```
nix run github:meshcore-dev/meshcore-cli#meshcore-cli
```

Version is defined in `pyproject.toml` (`project.version`) and echoed by `meshcli -v`; bump both together when cutting a release (see `version()` in `src/meshcore_cli/meshcore_cli.py`).

## Architecture

The entire CLI lives in one large module: `src/meshcore_cli/meshcore_cli.py` (~5300 lines). There is no package-internal layering beyond this file plus thin `__init__.py`/`__main__.py` shims.

### Execution flow

1. `cli()` → `asyncio.run(main(argv))`.
2. `main()` parses `getopt`-style flags (connection type/address, `-j` json mode, `-D` debug, `-S`/`-l` device scan/select, `-r` repeater serial mode, etc.), establishes the `MeshCore` connection (BLE via `bleak`, TCP, or serial), then either:
   - runs the commands passed on the command line through `process_cmds`, or
   - falls into `interactive_loop()` (the chat/REPL mode, default when no commands given or `-i` is passed).
3. Repeater serial mode (`-r`) is a separate code path (`setup_repeater_serial`, `repeater_loop`, `process_repeater_line`) that talks raw text CLI over serial instead of the structured `meshcore` protocol — used for line editing/history/completion/time-sync on repeaters that don't run the companion protocol.

### Command dispatch

- `next_cmd(mc, cmds, ...)` is the command dispatcher: a single giant `match cmd:` block (~2000 lines, from line ~2230) mapping every CLI command/alias to its async implementation. It returns `(remaining_cmds, output_str)` so commands can be chained on one line.
- `process_cmds` loops over `next_cmd` until the command list is exhausted.
- A leading `.` on a command forces JSON output for that invocation regardless of global `-j`.
- A leading `?` on a command routes to `get_help_for()` instead of executing it.
- New CLI commands are added as a new `case "name" | "alias":` branch inside `next_cmd`, plus corresponding entries in `command_help()` / `get_help_for()` for `?cmd` and the `help` command, and often in `make_completion_dict()` for tab-completion in interactive mode.

### Interactive/chat mode

- `interactive_loop()` implements the REPL (prompt via `prompt_toolkit`, history, completion via `MyNestedCompleter`/`make_completion_dict`).
- Concepts specific to this mode: a "current contact" (`to <dest>`), flood *scope* (region-limited packet diffusion, `%scope` suffix), `/`-prefixed commands to bypass the current contact, aliases (`alias`/`@name`, backed by `aliases_load`/JSON files), and shell redirection (`>`, `>>`, `|` for output; `<name|` for piping shell output into a command line as a placeholder).
- `process_line` / `process_pipeline` / `process_redirected_line` / `process_slash_cmd` / `process_contact_chat_line` implement this line-parsing/redirection layer on top of `next_cmd`.
- `apply_command_to_contacts` implements the `apply_to`/`at` batch command (filter contacts by type/hops/last-update, then run a command chain against each match).

### Event handling

- Async event handlers (`handle_log_rx`, `handle_advert`, `handle_path_update`, `handle_new_contact`, `handle_message`, `process_event_message`) are registered against the `meshcore` library's event system and print/relay incoming radio events (rx log, adverts, messages, contact/path updates) to the terminal or to attached handler processes.
- `handler_attach`/`handler_detach` let external shell processes subscribe to `rxlog` or `msgs` streams (`write_handler`/`relay_handler_output`, `enqueue_handler_event`).

### Configuration

- Config/state lives in `$HOME/.config/meshcore` (module-level constants like `MCCLI_ADDRESS` point here): remembered BLE address, prompt history, and optional `init` / `<device-name>.init` scripts auto-run before command-line commands.
- No config or secrets should be read from or written to any other location.

### Companion helper scripts

`scripts/` and `sxmo/` contain standalone shell/Python helpers (not part of the installed package) that pipe JSON output from `meshcore-cli` into external tools (e.g. `coords2img` map rendering, `geoclue` position queries, Sxmo phone integration). See `scripts/README.md` for the redirection/alias patterns they rely on (`|cmd`, `<|`, `{}` placeholders).

## Conventions to follow when editing `meshcore_cli.py`

- Command implementations return human-readable text by default and JSON when `json_output` is true (or the command was `.`-prefixed) — always support both output modes for a new/changed command, matching the existing `if json_output: ... else: ...` pattern.
- Commands that talk to the device go through `mc.commands.*` (the `meshcore` library's command API) and check `res.type == EventType.ERROR` before treating a response as success.
- Keep short aliases/shortcuts consistent with the table in `README.md`'s "Available Commands" section — update the README table when adding, renaming, or removing a command or alias.
