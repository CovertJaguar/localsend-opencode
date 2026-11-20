# localsend-opencode

An agent skill that wraps a [LocalSend](https://localsend.org) CLI, so an agent
can move files to and from devices on the local network (or by IPv6) without a
GUI. Written for OpenCode, loads unchanged in Claude Code, and runs under any
local CLI agent that can execute a Python script.

The CLI itself is vendored as a git subtree at
`skills/localsend/vendor/localsend-cli` from
[CovertJaguar/localsend-cli](https://github.com/CovertJaguar/localsend-cli)
(branch `feat/session-events`), which carries these upstream fixes:

- `POST /v2/register` answered plain text `OK`, so clients expecting the device
  info JSON dropped the receiver from their device list
- uploads sent with `Transfer-Encoding: chunked` (what the official apps do)
  were saved as 0 bytes, because only `Content-Length` was read
- the receiver bound `0.0.0.0`, so it never answered an IPv6 sender
- completion was invisible from outside the process, so callers polled the save
  folder; `receive --event-log` and `--on-complete` now report it
- sends presented no client certificate, which LocalSend 2.1+ receivers reject
  with `TLSV13_ALERT_CERTIFICATE_REQUIRED`

## Install

The skill is a directory — `SKILL.md`, references, scripts and the vendored
CLI. Copy it where the host looks for skills; there is no build step, no
package to install, and no dependency beyond Python 3.8+ and `openssl`.

### OpenCode

```sh
mkdir -p ~/.config/opencode/skills
cp -r skills/localsend ~/.config/opencode/skills/localsend
```

Or point OpenCode at the checkout instead of copying, in `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": ["~/path/to/localsend-opencode/skills"],
}
```

Restart the service (`opencode service restart`) or start a new session, then
the skill is available as `localsend`.

### Claude Code

Claude Code reads the same `SKILL.md` frontmatter, so nothing needs converting:

```sh
mkdir -p ~/.claude/skills
cp -r skills/localsend ~/.claude/skills/localsend
```

Use `.claude/skills/localsend` inside a repository for a project-scoped skill
instead. On Windows the destination is `%USERPROFILE%\.claude\skills\localsend`.

This skill fits Claude Code's execution model exactly: it runs commands on your
machine, so the LAN side works as written, and background shell jobs report
completion, which is what `wait-transfer.py` blocks on.

### Other hosts

- **Local CLI agents without a skill loader** (Codex CLI, and similar): run the
  commands directly, or copy the Receive and Wait-for-it-to-land sections into
  `AGENTS.md`. Nothing in the skill depends on a loader — the CLI is a Python
  script and the waiter is stdlib-only.
- **Hosted agents** (ChatGPT, Grok, any cloud sandbox): cannot run this. They
  have no route to your LAN and no inbound port for the receiver, so discovery
  and transfer both fail — the same way they do inside a container without
  multicast.

## Updating the vendored CLI

```sh
git subtree pull --prefix skills/localsend/vendor/localsend-cli \
  git@github.com:CovertJaguar/localsend-cli.git feat/session-events --squash
```

## Layout

```
skills/localsend/
├── SKILL.md
├── references/
│   └── ops-notes.md
├── scripts/
│   └── wait-transfer.py   # blocks on the event log, prints a verdict
└── vendor/
    └── localsend-cli/     # git subtree
```

## Licence

The skill is MIT. The vendored CLI keeps its own MIT licence (see
`vendor/localsend-cli/LICENSE`).
