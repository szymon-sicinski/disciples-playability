# cnc-ddraw — provenance

Record of the exact upstream artifact this project's wrapper fetches and pins.
This is a **third-party archive** (MIT-licensed), not game data, so its digest
is recorded in full — the no-game-hashes rule does not apply to it.

| Field | Value |
|---|---|
| Project | [`FunkyFr3sh/cnc-ddraw`](https://github.com/FunkyFr3sh/cnc-ddraw) |
| Licence | MIT (`LICENSE` in the repo; the text is shipped here as `cnc-ddraw-LICENSE.txt`) |
| Release tag | `v7.1.0.0` |
| Release date | 2024-12-28 |
| Asset name | `cnc-ddraw.zip` |
| Byte size | 2,688,079 |
| SHA-256 of the zip | `0b13ab89a64c9918189b1dadd449ef6ed3cb3b7b19cabd96d8adbd95505bb908` |
| Download URL | `https://github.com/FunkyFr3sh/cnc-ddraw/releases/download/v7.1.0.0/cnc-ddraw.zip` |

The SHA-256 was **measured** (not copied from prose) on 2026-11-21 by
downloading the asset and running `sha256sum`; the command is recorded in the
card that introduced it. It is the value pinned as `CNC_DDRAW_SHA256` in
`src/disciples_play/wrapper.py`.

## What ships and what does not

- **Never vendored.** The release zip (and therefore `ddraw.dll`) is not
  committed to this repository. `disciples_play.wrapper.fetch_wrapper()` can
  download it from the pinned tag and verifies the digest above, but **no CLI
  command invokes it in v0.1** — the file is copied into `Exe/` by hand.
- **Licence shipped.** `cnc-ddraw-LICENSE.txt` (verbatim upstream `LICENSE`) is
  committed so the MIT notice travels with the fetch code.
- **Update procedure.** To move to a new release: bump `CNC_DDRAW_TAG` and
  `CNC_DDRAW_SHA256` in `src/disciples_play/wrapper.py`, re-measure the new
  asset's SHA-256 by hand (never trust a digest in prose), and update the byte
  size and digest in this file and in `THIRD_PARTY.md`. If the digest is not
  updated, `fetch_wrapper` refuses the download on mismatch — by design.
