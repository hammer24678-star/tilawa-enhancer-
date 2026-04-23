#!/data/data/com.termux/files/usr/bin/bash
# run_s23.sh — S23 background runner
# Runs Parts 1, 2, 3 sequentially. Logs everything to a file.
# Can run in background — safe to minimize Termux.
#
# Usage:
#   cd ~/tilawa-enhancer
#   bash run_s23.sh            # runs in foreground (you see output)
#   bash run_s23.sh --bg       # runs in background (you get tail -f command)
#   bash run_s23.sh --part 2   # run only Part 2 (1, 2, or 3)
#   bash run_s23.sh --bg --part 3   # background, Part 3 only

set -euo pipefail

# ── config ───────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/tilawa_s23_${TIMESTAMP}.log"
PID_FILE="$LOG_DIR/tilawa_s23.pid"

START_PART=1
END_PART=3
BG_MODE=0

# ── parse args ───────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bg)       BG_MODE=1; shift ;;
        --part)     START_PART="$2"; END_PART="$2"; shift 2 ;;
        --from)     START_PART="$2"; shift 2 ;;
        --to)       END_PART="$2"; shift 2 ;;
        --log)      LOG_FILE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: bash run_s23.sh [--bg] [--part 1|2|3] [--from N] [--to N]"
            echo "  --bg        run in background (nohup)"
            echo "  --part N    run only part N"
            echo "  --from N    start from part N"
            echo "  --to N      stop after part N"
            echo "  --log FILE  write log to FILE (default: ~/tilawa_s23_TIMESTAMP.log)"
            exit 0
            ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── if --bg, re-launch ourselves under nohup and exit ────────────────────────
if [[ $BG_MODE -eq 1 ]]; then
    echo "Starting S23 in background..."
    echo "Log file: $LOG_FILE"
    echo ""

    # Remove --bg from args to avoid infinite re-launch
    ARGS=""
    [[ $START_PART -ne 1 || $END_PART -ne 3 ]] && ARGS="--from $START_PART --to $END_PART"

    nohup bash "$0" $ARGS --log "$LOG_FILE" > "$LOG_FILE" 2>&1 &
    BG_PID=$!
    echo "$BG_PID" > "$PID_FILE"

    echo "Background PID: $BG_PID"
    echo "PID file: $PID_FILE"
    echo ""
    echo "Monitor progress:"
    echo "  tail -f $LOG_FILE"
    echo ""
    echo "Stop if needed:"
    echo "  kill $BG_PID"
    echo ""
    echo "Starting tail (Ctrl+C to detach from log, process keeps running):"
    sleep 1
    tail -f "$LOG_FILE"
    exit 0
fi

# ── foreground run ────────────────────────────────────────────────────────────
run_part() {
    local PART_NUM=$1
    local SCRIPT="tilawa_fix_s23_part${PART_NUM}.py"

    if [[ ! -f "$SCRIPT_DIR/$SCRIPT" ]]; then
        echo "[ERROR] $SCRIPT not found in $SCRIPT_DIR"
        return 1
    fi

    echo ""
    echo "================================================================"
    echo "  STARTING PART $PART_NUM  --  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "================================================================"
    echo ""

    # -u = unbuffered python output (so tail -f shows in real time)
    python3 -u "$SCRIPT_DIR/$SCRIPT"
    local EXIT_CODE=$?

    echo ""
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo "  [Part $PART_NUM] PASSED (exit 0) -- $(date '+%H:%M:%S')"
    else
        echo "  [Part $PART_NUM] FAILED (exit $EXIT_CODE) -- $(date '+%H:%M:%S')"
        echo "  Stopping. Review output above and re-run when ready."
    fi
    echo ""
    return $EXIT_CODE
}

# ── header ────────────────────────────────────────────────────────────────────
echo "================================================================"
echo "  TILAWA S23 FIX RUNNER"
echo "  Parts: $START_PART -> $END_PART"
echo "  Started: $(date '+%Y-%m-%d %H:%M:%S')"
if [[ -n "${LOG_FILE:-}" && "$LOG_FILE" != "/dev/null" ]]; then
    echo "  Log: $LOG_FILE"
fi
echo "================================================================"

cd "$SCRIPT_DIR"

OVERALL_OK=0
for PART in $(seq $START_PART $END_PART); do
    if run_part "$PART"; then
        echo "  Part $PART complete. Waiting 30s before next part..."
        sleep 30
    else
        OVERALL_OK=1
        break
    fi
done

echo "================================================================"
if [[ $OVERALL_OK -eq 0 ]]; then
    echo "  ALL PARTS COMPLETE -- $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    echo "  Verification:"
    echo "    curl -s https://carm5333-tilawa-server.hf.space/"
    echo "    Expected: engines all true, refs=3, status=ok"
else
    echo "  RUN FAILED -- see output above"
    echo "  Fix the issue and re-run from the failed part:"
    echo "    bash run_s23.sh --from PART_NUMBER"
fi
echo "================================================================"
exit $OVERALL_OK
