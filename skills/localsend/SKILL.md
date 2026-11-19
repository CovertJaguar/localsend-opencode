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
  --save-dir ~/Downloads/localsend
```

- `-y` auto-accepts every transfer. Without it the CLI prompts, which is
  unusable when nobody is at the machine.
- `--alias` must come **before** the subcommand.
- Confirm it is listening before telling the user to send:

```sh
curl -k -s https://127.0.0.1:53317/api/localsend/v2/info
```

That must return JSON with `"alias"`, `"fingerprint"` and `"port"`. An empty
reply or connection refused means the receiver is not running — check the
process, do not ask the user to retry.

State the exact destination when handing off: device alias, IP and port,
protocol `https`, and where files will land.

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

A transfer is not done because the command exited cleanly. Check the file:

```sh
ls -l ~/Downloads/localsend
sha256sum ~/Downloads/localsend/<file>
```

Zero-byte files mean the receiver could not read the request body; see
`references/ops-notes.md`. An empty file that "succeeded" is the most common
false positive.

## Etiquette

- Never edit the vendored copy in place to fix a transfer bug. Fix it in the
  upstream CLI repo you vendor from (ours:
  `CovertJaguar/localsend-cli`), then
  `git subtree pull --prefix skills/localsend/vendor/localsend-cli ...`.
- Do not leave a receiver running with `-y` for longer than the transfer needs;
  it accepts from anyone who can reach the port.
- When a transfer fails, report which layer failed: discovery, TLS connect,
  `/register`, `/prepare-upload`, or the upload body. Each has a different
  fix and the CLI's own messages usually do not say which.
