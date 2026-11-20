---
name: LocalSend
description: Send or receive files over the LAN or by IPv6 with the vendored LocalSend CLI — headless transfers to phones and desktops without a GUI, including the gotchas that make stock clients fail silently.
---

# LocalSend

Move files between this machine and any device running LocalSend (Android,
iOS, Windows, macOS, Linux). The CLI is vendored at
`vendor/localsend-cli/localsend-cli` — a single-file Python script, no install
step. Read `references/ops-notes.md` before debugging a failed transfer; it
lists the failure modes that produce no useful error.

## Before anything

The script shells out to `openssl` to mint its self-signed certificate.

```sh
localsend-cli --version 2>/dev/null || echo "use: python3 vendor/localsend-cli/localsend-cli"
```

- macOS and Linux ship `openssl`; on Windows add Git's copy for the session:
  `export PATH="/c/Program Files/Git/usr/bin:$PATH"` (bash) or prepend
  `C:\Program Files\Git\usr\bin` to `PATH` (PowerShell).
- Python 3.8+. No pip packages.
- Port `53317` TCP must be free and allowed inbound by the firewall. If it is
  taken the CLI falls back to `53318`/`53319` and reports the real port.

## Discover

```sh
python3 vendor/localsend-cli/localsend-cli discover -t 2
python3 vendor/localsend-cli/localsend-cli discover --json -t 2
```

Devices appear when their app is open on the same L2 network. Multicast is
unreliable on some Wi-Fi setups, so a device that is reachable by IP but never
listed is expected — send to its address instead.

## Receive

Run this in the background, because it blocks:

```sh
python3 vendor/localsend-cli/localsend-cli --alias "$(hostname)" receive -y \
  --save-dir ~/Downloads/localsend \
  --event-log ~/Downloads/localsend/.events.jsonl
```

- `-y` auto-accepts every transfer. Without it the CLI prompts, which is
  unusable when nobody is at the machine.
- `--alias` must come **before** the subcommand.
- `--event-log` appends JSONL progress; `--on-complete CMD` runs a shell
  command per finished session. Both are plain files and subprocesses, so the
  signal is identical on Windows, macOS and Linux.
- Confirm it is listening before telling the user to send:

```sh
curl -k -s https://127.0.0.1:53317/api/localsend/v2/info
```

That must return JSON with `"alias"`, `"fingerprint"` and `"port"`. An empty
reply or connection refused means the receiver is not running — check the
process, do not ask the user to retry.

State the exact destination when handing off: device alias, IP and port,
protocol `https`, and where files will land.

Whether the receiver stays up after the transfer is a judgement call, not a
default: see Etiquette for the criteria and say which way you went.

## Wait for it to land

Do not poll the save folder. A folder that stops changing looks the same
whether the batch finished or the sender stalled mid-file, and no timeout
separates the two — a 2 GB file on slow Wi-Fi can sit still longer than any
sensible debounce. The receiver is handed the manifest before the first byte
arrives and records `session_complete` only once the last expected file has
landed, so block on that record instead:

```sh
python3 scripts/wait-transfer.py \
  --event-log ~/Downloads/localsend/.events.jsonl --timeout 900
```

Run it in the background so its exit resumes you. It prints one line per file
with the SHA-256, compares every saved size against the announced one, and
exits `0` when all match, `2` when a file is short or missing (the classic
zero-byte false positive), `124` on timeout.

For unattended machines, `--on-complete` takes any shell command —
`notify-send`, `osascript -e 'display notification'`, `msg`, or a webhook. It
runs with `LOCALSEND_OK`, `LOCALSEND_REPORT` (path to a JSON report),
`LOCALSEND_SESSION` and `LOCALSEND_SAVE_DIR` in the environment.

## Send

```sh
python3 vendor/localsend-cli/localsend-cli send --to "Fast Potato" photo.jpg
python3 vendor/localsend-cli/localsend-cli send --to 192.168.1.20 report.pdf
```

`--to` accepts an alias substring or an IP address; an IP is probed directly
over HTTPS on 53317. Multiple files and directories are allowed and directories
are collected recursively. There is no non-interactive accept on the receiving
side — if the receiver is a person, they must click Accept.

## Verify

A transfer is not done because the command exited cleanly. With `--event-log`
the records already carry `sha256`, `bytes`, `declared_bytes` and `ok` per
file; trust `ok`, not the sender's `200`. Without an event log, check by hand:

```sh
ls -l ~/Downloads/localsend
sha256sum ~/Downloads/localsend/<file>
```

Zero-byte files mean the receiver could not read the request body; see
`references/ops-notes.md`. An empty file that "succeeded" is the most common
false positive, and the event log reports it as `ok: false`.

## Etiquette

- Never edit the vendored copy in place to fix a transfer bug. Fix it in the
  upstream CLI repo you vendor from (ours:
  `CovertJaguar/localsend-cli`), then
  `git subtree pull --prefix skills/localsend/vendor/localsend-cli ...`.
- Decide from context whether the receiver should outlive the transfer, and say
  which you chose in a sentence rather than asking. Stop it when the reason it
  was started is satisfied and nothing points to another send: a one-shot
  request whose file has landed, a batch the user called complete, the end of
  the task, an unattended machine, or a network you do not trust. Keep it when
  the user signals more is coming — they said so, they are iterating ("try
  again", "now this one"), the announced manifest still has files outstanding,
  or they are mid-test and the next send is minutes away. When the context is
  genuinely ambiguous, close it after the current session: `-y` accepts from
  anyone who can reach the port, and restarting costs one command, so the cheap
  mistake is a closed receiver.
- Stop the waiter with the receiver. A `wait-transfer.py` left behind holds no
  port, but it lingers until its timeout and will report the next transfer the
  receiver never saw.
- When a transfer fails, report which layer failed: discovery, TLS connect,
  `/register`, `/prepare-upload`, or the upload body. Each has a different
  fix and the CLI's own messages usually do not say which.
