# localsend-opencode

An OpenCode skill that wraps a [LocalSend](https://localsend.org) CLI, so an
agent can move files to and from devices on the local network (or by IPv6)
without a GUI.

The CLI itself is vendored as a git subtree at
`skills/localsend/vendor/localsend-cli` from
[CovertJaguar/localsend-cli](https://github.com/CovertJaguar/localsend-cli)
(branch `fix/register-chunked-ipv6`), which carries two upstream bugs fixed:

- `POST /v2/register` answered plain text `OK`, so clients expecting the device
  info JSON dropped the receiver from their device list
- uploads sent with `Transfer-Encoding: chunked` (what the official apps do)
  were saved as 0 bytes, because only `Content-Length` was read

plus one local fix:

- the receiver bound `0.0.0.0`, so it never answered an IPv6 sender

## Install

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

## Updating the vendored CLI

```sh
git subtree pull --prefix skills/localsend/vendor/localsend-cli \
  git@github.com:CovertJaguar/localsend-cli.git fix/register-chunked-ipv6 --squash
```

## Layout

```
skills/localsend/
├── SKILL.md
├── references/
│   └── ops-notes.md
└── vendor/
    └── localsend-cli/     # git subtree
```

## Licence

The skill is MIT. The vendored CLI keeps its own MIT licence (see
`vendor/localsend-cli/LICENSE`).
