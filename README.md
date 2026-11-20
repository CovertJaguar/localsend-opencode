# localsend-opencode

An agent skill that wraps a [LocalSend](https://localsend.org) CLI: move files
to and from devices on the local network (or by IPv6) without a GUI. Loads in
OpenCode and Claude Code, and runs under any local agent that can execute a
Python script.

## What it does

- **Receive** — auto-accepts transfers into a directory and records each one as
  JSON: announced size, bytes on disk, SHA-256, and whether they match.
- **Send** — pushes files or directories to a device by alias or IP.
- **Wait** — `scripts/wait-transfer.py` blocks until a transfer finishes and
  exits `0` verified, `2` short or missing, `124` timeout.
- **Notify** — `--on-complete CMD` runs a shell command per finished transfer,
  with `LOCALSEND_OK`, `LOCALSEND_REPORT`, `LOCALSEND_SESSION` and
  `LOCALSEND_SAVE_DIR` in the environment.

## How it works

LocalSend v2 over HTTPS on port `53317`, self-signed certificates, presenting a
client certificate to receivers that require mutual TLS. The receiver is given
the whole file manifest before the first byte arrives, so completion is a
protocol fact rather than something inferred from file timestamps: it appends
`session_start`, `file_saved` and `session_complete` records to the event log.

The CLI is vendored at `skills/localsend/vendor/localsend-cli` from
[CovertJaguar/localsend-cli](https://github.com/CovertJaguar/localsend-cli).
Single-file Python plus stdlib-only helpers — no pip packages. Needs Python
3.8+, `openssl`, and port `53317` reachable inbound.

## Run it

```sh
# receive, verifying and logging every transfer
python3 vendor/localsend-cli/localsend-cli receive -y \
  --save-dir ~/Downloads/localsend \
  --event-log ~/Downloads/localsend/.events.jsonl

# send
python3 vendor/localsend-cli/localsend-cli send --to "Phone" photo.jpg

# block until the next transfer lands, then print a verdict
python3 scripts/wait-transfer.py --event-log ~/Downloads/localsend/.events.jsonl
```

`--alias NAME` goes before the subcommand; `send --ip <addr>` skips discovery.

### Install as a skill

**OpenCode**

```sh
mkdir -p ~/.config/opencode/skills
cp -r skills/localsend ~/.config/opencode/skills/localsend
```

or reference the checkout in `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": ["~/path/to/localsend-opencode/skills"],
}
```

**Claude Code**

```sh
mkdir -p ~/.claude/skills
cp -r skills/localsend ~/.claude/skills/localsend
```

Inside a repository, `.claude/skills/` scopes it to that project. On Windows the
destination is `%USERPROFILE%\.claude\skills\localsend`.

**Anything else** — local CLI agents without a skill loader can run the commands
directly or copy the Receive sections into `AGENTS.md`. Hosted agents (ChatGPT,
Grok, cloud sandboxes) cannot: no route to the LAN, no inbound port.

## Licence

The skill is MIT. The vendored CLI keeps its own MIT licence
(`vendor/localsend-cli/LICENSE`).
