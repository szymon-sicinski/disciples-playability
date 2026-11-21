#!/usr/bin/env bash
#
# probe-matrix.sh — run the four DDraw × PaletteAnim combinations from the
# plan's E2/E3 experiments (docs/plans/00-playability-plan.md §7, risks R2/R3)
# and record the answers the maintainer types, so they can be pasted back.
#
# Non-destructive: the install's Exe/DISCIPLE.INI is copied to a temp dir
# before anything runs, and restored (via a trap) when the script exits, so
# whatever happens — including Ctrl-C — the install is left as it was found.
#
# Interactive by design: it asks one question per combination, so it refuses
# to run without a terminal rather than hang a CI job or an agent.

set -euo pipefail

usage() {
    cat <<'EOF'
usage: probe-matrix.sh --game-dir DIR [--report FILE] [--wine PATH]

Runs four combinations — cnc-ddraw on/off × PaletteAnim 0/1 — asks one
question after each, and appends the answers to the report file.

  --game-dir DIR   the Disciples install (or a parent of it)
  --report FILE    where answers are appended (default: ./probe-report.txt)
  --wine PATH      wine binary (default: wine on PATH)
EOF
}

GAME_DIR=""
REPORT="probe-report.txt"
WINE="wine"

while [ $# -gt 0 ]; do
    case "$1" in
        --game-dir) GAME_DIR="$2"; shift 2 ;;
        --report) REPORT="$2"; shift 2 ;;
        --wine) WINE="$2"; shift 2 ;;
        -h | --help) usage; exit 0 ;;
        *) echo "probe-matrix.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# Never hang a CI job or an agent: require a terminal on stdin and stdout.
if [ ! -t 0 ] || [ ! -t 1 ]; then
    echo "probe-matrix.sh: needs an interactive terminal (it asks for your answers)." >&2
    exit 64
fi

if [ -z "$GAME_DIR" ]; then
    echo "probe-matrix.sh: --game-dir is required" >&2
    usage >&2
    exit 2
fi
if [ ! -d "$GAME_DIR" ]; then
    echo "probe-matrix.sh: not a directory: $GAME_DIR" >&2
    exit 2
fi

# Resolve the Exe directory: Exe/Disciple.exe, one or two levels down (the
# same shape the launcher accepts). ``-exec dirname`` prints only the parent
# directory of the first match, then ``-quit`` stops.
EXE_DIR=$(find "$GAME_DIR" -maxdepth 4 -type f -iname 'Disciple.exe' -exec dirname {} \; -quit 2>/dev/null || true)
if [ -z "$EXE_DIR" ] || [ ! -f "$EXE_DIR/Disciple.exe" ]; then
    echo "probe-matrix.sh: Disciple.exe not found under $GAME_DIR" >&2
    exit 2
fi

# Locate the INI case-insensitively.
INI_PATH=$(find "$EXE_DIR" -maxdepth 1 -type f -iname 'DISCIPLE.ini' -print -quit 2>/dev/null || true)
if [ -z "$INI_PATH" ]; then
    echo "probe-matrix.sh: DISCIPLE.INI not found in $EXE_DIR" >&2
    exit 2
fi

DDRAW_DLL="$EXE_DIR/ddraw.dll"

# Non-destructive: back the INI (and any staged ddraw.dll) up to a temp dir,
# and restore both on exit.
WORK_DIR=$(mktemp -d)
INI_BACKUP="$WORK_DIR/DISCIPLE.INI.bak"
DLL_BACKUP="$WORK_DIR/ddraw.dll.bak"
STASH="$WORK_DIR/ddraw.dll.stashed"
cp "$INI_PATH" "$INI_BACKUP"
HAD_DLL=0
if [ -f "$DDRAW_DLL" ]; then
    cp "$DDRAW_DLL" "$DLL_BACKUP"
    HAD_DLL=1
fi

restore() {
    cp "$INI_BACKUP" "$INI_PATH"
    if [ "$HAD_DLL" -eq 1 ]; then
        cp "$DLL_BACKUP" "$DDRAW_DLL"
    else
        rm -f "$DDRAW_DLL"
    fi
    rm -rf "$WORK_DIR"
}
trap restore EXIT

# Set paletteanim=0/1 in the INI, preserving the rest of the line (and CRLF).
set_paletteanim() {
    # Match only the digits after paletteanim= so the CRLF terminator survives.
    sed -i -E "s/paletteanim=[0-9]+/paletteanim=$1/" "$INI_PATH"
}

# Move ddraw.dll aside for the built-in-ddraw runs, and back for cnc-ddraw.
set_cnc_ddraw() {
    if [ "$1" = on ]; then
        if [ ! -f "$DDRAW_DLL" ] && [ -f "$STASH" ]; then
            mv "$STASH" "$DDRAW_DLL"
        fi
        if [ ! -f "$DDRAW_DLL" ]; then
            echo "probe-matrix.sh: cnc-ddraw=on needs ddraw.dll next to Disciple.exe; skipping." >&2
            return 1
        fi
    elif [ -f "$DDRAW_DLL" ]; then
        mv "$DDRAW_DLL" "$STASH"
    fi
    return 0
}

record() {
    printf '%s\n' "$1" >>"$REPORT"
}

echo "probe-matrix.sh: game   $EXE_DIR"
echo "probe-matrix.sh: report $REPORT"
echo

# cnc-ddraw on/off × paletteanim 0/1. Baseline first, matching the plan.
for combo in off:1 off:0 on:1 on:0; do
    cnc=${combo%%:*}
    pal=${combo##*:}

    set_cnc_ddraw "$cnc" || continue
    set_paletteanim "$pal"

    if [ "$cnc" = on ]; then
        override="ddraw=n,b"
    else
        override=""
    fi

    echo "--------------------------------------------------------------------------------"
    echo "combo: cnc-ddraw=$cnc  paletteanim=$pal"
    echo "run:   (cd $EXE_DIR && WINEDLLOVERRIDES='$override' $WINE Disciple.exe)"
    echo "watch: palette animation (water/fire/rain/animated cursor) — no stripes or stuck colours?"
    echo "When you have quit the game, type your answer."

    if ! (cd "$EXE_DIR" && env WINEDLLOVERRIDES="$override" "$WINE" Disciple.exe); then
        record "$(date -Is) cnc-ddraw=$cnc paletteanim=$pal -> LAUNCH-FAILED"
        echo "launch failed; recorded as LAUNCH-FAILED."
        continue
    fi

    printf 'answer (y/n/skip): '
    read -r answer
    case "$answer" in
        y | Y | yes | YES) verdict="OK" ;;
        n | N | no | NO) verdict="BROKEN" ;;
        *) verdict="SKIPPED ($answer)" ;;
    esac
    record "$(date -Is) cnc-ddraw=$cnc paletteanim=$pal -> $verdict"
    echo "recorded: cnc-ddraw=$cnc paletteanim=$pal -> $verdict"
    echo
done

echo "done. Report written to $REPORT — paste the lines back into the card."
