# LocalSend failure modes

Everything here was observed on real transfers, not inferred from the spec.
Each entry says what you see, why it happens, and what actually fixes it.

## The five layers

A transfer passes through five distinct stages. The CLI only reports the last
one it reached, so identify the stage first — the message "transfer failed"
almost never says which layer broke.

1. **Discovery** — UDP multicast `224.0.0.167:53317`, or `POST /register` for
   HTTP-scan discovery.
2. **TLS connect** — HTTPS with a self-signed certificate.
3. **`/api/localsend/v2/prepare-upload`** — sender announces file list, receiver
   replies with `{sessionId, files: {fileId: token}}`.
4. **`/api/localsend/v2/upload?sessionId=&fileId=&token=`** — file bytes.
5. **`/api/localsend/v2/cancel`** — only on abort.

## Symptom: `404` on send

The receiver does not implement the route the sender used.

LocalSend has two route generations. Older clients and some implementations
still POST `/api/localsend/v1/send-request` and `/api/localsend/v1/send`.
A receiver that only serves `/v2/...` answers `404 page not found`.

Modern implementations also need `POST /api/localsend/v2/register`; without it,
HTTP-scan discovery (what Android relies on) silently omits the receiver.

## Symptom: `TLSV13_ALERT_CERTIFICATE_REQUIRED` on send

The receiver wants mutual TLS and the sender presented no client certificate.
LocalSend 2.1+ receivers request one during the handshake; a client that only
verifies the server's self-signed certificate gets this alert instead of an
HTTP status, so nothing appears in the receiver's transfer log — the connection
dies before `/prepare-upload`.

The sender's certificate is the same self-signed one it already generates at
startup, and its fingerprint is what goes in `info.fingerprint`, so presenting
it is all that is needed: load the cert chain into the client SSL context for
the prepare-upload and upload requests. Sending without it works against older
receivers and fails against current ones, which makes this look like a
per-device problem rather than a protocol mismatch.

## Symptom: `error decoding response body ... expected value at line 1 column 1`

The `/register` reply was not JSON. Clients decode that response into a device
object, so a `200 OK` with a plain-text body such as `OK` fails the same way an
empty response does.

`/register` must return the same device info as `/info`: `alias`, `version`,
`deviceModel`, `deviceType`, `fingerprint`, `port`, `protocol`, `download`.

## Symptom: file saved as 0 bytes, everything reported success

The sender streamed the body with `Transfer-Encoding: chunked` and no
`Content-Length`; the receiver read `Content-Length`, got `0`, and wrote an
empty file. The official apps do this for every upload, so a receiver that only
handles `Content-Length` fails on all of them while still answering `200`.

Two tells in a server log: a `400 Bad request syntax ('80000')` right after the
upload line (`80000` is the hex chunk size being parsed as the next request),
and a saved file of exactly zero bytes.

The fix is to decode chunked framing, falling back to `Content-Length` when the
header is absent.

## Symptom: connection refused, nothing in the receiver log

The listener is bound to one address family only.

A server bound to `0.0.0.0` is IPv4-only and refuses every IPv6 connection
before HTTP starts — no log line, no TLS handshake, nothing. This bites when the
sender uses an IPv6 literal, a WAN address, or a v6-only LAN.

Bind `::` with `IPV6_V6ONLY` cleared so a single socket serves both families.
On Windows the default for `IPV6_V6ONLY` is not reliably off across Python
versions, so set it explicitly in `server_bind()`.

## Symptom: receiver disappears mid-transfer

Background processes are tied to the shell that started them. A receiver
started from a tool shell can be reaped when that shell exits, closing the port
between the user's attempt and the transfer.

Start long-lived receivers detached from the calling process, and check the
port is still open before asking anyone to retry.

## Symptom: sender cannot find the device at all

- Both devices must be on the same L2 network for multicast.
- Access-point isolation, guest networks and many VPNs block multicast and
  often the transfer too.
- Windows treats an unknown network as Public and blocks inbound by default.
- Send by IP address to bypass discovery entirely.

## Symptom: "is it done?" has no reliable answer

Watching the save folder cannot answer it. A finished batch and a stalled one
look identical once nothing has been written for a while, and the gap between
files in a batch is unbounded: multi-gigabyte files, throttled phones, AP
retries and disk stalls all produce silences longer than any debounce, while a
crashed sender produces one that never ends. mtime-debounce watchers therefore
truncate big batches and call dead transfers complete.

The protocol already answers it. `prepare-upload` carries the whole manifest,
and the receiver prints `All N file(s) received` only when the last expected
file has landed. `--event-log` writes that same fact as JSON Lines — announced
size, bytes written, SHA-256 and an `ok` flag per file — and `--on-complete`
runs a command per finished session. Both are plain files and subprocesses, so
they behave identically on Windows, macOS and Linux, unlike inotify or
ReadDirectoryChangesW watchers.

The CLI line-buffers its own stdout, so tailing the log is not stuck behind a
block buffer. Parsing that text is still coupled to its wording, and it still
cannot tell a paused session from an abandoned one — key off
`session_complete`, not off silence.

## Wrong diagnosis to avoid

A patcher, a log line, or a mentioned mod name is not proof of cause. In this
tool the frequent traps are:

- blaming the firewall when the receiver is not running at all
- blaming TLS when the port never accepted the connection
- blaming the sender when the receiver wrote 0 bytes
- treating a `200` as success without checking the saved file's size and hash
