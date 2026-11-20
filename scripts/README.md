# scripts

Automation that runs on the **maintainer's machine**, not in CI — the sandbox
has no Wine and no display, so anything that launches the game cannot be tested
by an agent.

| Script | Purpose | Milestone |
|---|---|---|
| `probe-matrix.sh` | Run the four `DDraw × PaletteAnim` combinations and write a report the human can paste back. | M4 |

Rules: read-only against the game install unless the script says otherwise and
takes an explicit flag; no game bytes leave the machine.
