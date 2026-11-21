# Development

Everything here is about working *on* the pack. Nothing here needs the game:
the test suite runs on synthetic fixtures only.

## Commit signing

Every commit after `df4c9f97` is SSH-signed with the maintainer's ED25519 key,
fingerprint `SHA256:ynVy0I8VpUSrsz/xadf4hqWzjtZvVF+Fb1xsJRNjs5s`
(`hermes-retrolab`). Signing is configuration, not convention — a fresh clone
has none of it, so repeat this once per clone.

### One-time setup in a clone

```bash
# 1. Let git verify SSH signatures locally: one line per trusted key.
#    The principal must be the committer email git will put on the commit.
mkdir -p ~/.config/git
printf '%s %s\n' "$(git config user.email)" "$(cat ~/.ssh/id_ed25519.pub)" \
  >> ~/.config/git/allowed_signers

# 2. Sign with SSH rather than GPG.
git config --local gpg.format ssh
git config --local user.signingkey ~/.ssh/id_ed25519.pub
git config --local gpg.ssh.allowedSignersFile ~/.config/git/allowed_signers
git config --local commit.gpgsign true
```

### Verifying a commit

```bash
git log -1 --format='%G?'                  # G = good signature, N = none
git cat-file -p HEAD | grep -c '^gpgsig'   # 1 = the signature is in the object
git log -1 --show-signature                # "Good \"git\" signature for <email>"
```

**Pitfall — `%G?` is not proof of absence.** With signing configured but
`gpg.ssh.allowedSignersFile` missing, or present without the committer's email,
git prints `N` for a *correctly signed* commit, and `--show-signature` reports:

```
error: gpg.ssh.allowedSignersFile needs to be configured and exist for ssh signature verification
```

That is indistinguishable from "unsigned" unless you read the raw object. The
authoritative check is the `gpgsig` header:

```bash
git cat-file -p <sha> | grep -c '^gpgsig'  # 0 = genuinely unsigned
```

GitHub shows the **Verified** badge only when the signature is valid *and* the
key is registered on the account as a signing key. Until then, a correctly
signed push still displays "Unverified" — that is a GitHub-side fact, not a
signing failure.

### Exception: `df4c9f97` is unsigned

The scaffold commit `df4c9f97` ("chore: scaffold the disciples-playability
repository", 2026-11-20) was made before this configuration existed and carries
no signature. It is published history on `main` and is deliberately **not**
rewritten: re-signing it would mean an amend plus a force-push of `main`, which
this project forbids. It is recorded here as a known exception rather than
quietly fixed. Whether history should be fully signed from commit one is the
maintainer's call.

## Local check loop

The same commands CI runs (`.github/workflows/tests.yml`), on Linux and
Windows, Python 3.10–3.13:

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest -q
disciples-play --help
```

CI additionally runs `disciples-play --help` on every matrix cell, so the
console-script entry point is exercised and not merely imported.

## Rules that bite

- **No game bytes, ever.** No `Disciple.exe`, `.DBF`/`.dbi` tables, art, audio,
  video, `.smk`, saves or INI files from an installation. `.gitignore` lists the
  extensions; do not weaken it. Before committing:
  `git ls-files | grep -Ei '\.(exe|dll|dbf|dbi|dlg|smk|wdb|sg|bin|cue|iso|img)$'`
  must print nothing.
- **Do not modify the game folder.** The pack reads it; the launcher rewrites
  `Exe/DISCIPLE.INI` in place (default `--ini-mode backup`, with a one-time
  backup named after whichever INI file it resolved — `DISCIPLE.INI.orig` or
  `DISCIPLE.ini.orig` on the lowercase install the game writes back) or, with
  `--ini-mode copy-tree`, in a sibling copy.
  Tests write only to synthetic fixtures, never the real installation.
- **Commit the plan verbatim.** `docs/plans/00-playability-plan.md` is a
  byte-for-byte copy of the plan the milestones are measured against. Do not
  reformat it.
