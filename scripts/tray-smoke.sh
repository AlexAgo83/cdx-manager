#!/usr/bin/env bash
# Manual smoke checks for the tray companion, on a real host.
#
# `item_085` asks for these to be run and recorded rather than asserted, because
# every one of them has already been wrong once on a real machine in a way no
# unit test noticed: a black glyph invisible on a dark taskbar, an icon buried in
# the Windows overflow, a trailing space in a cmd.exe environment variable.
#
# Read-only apart from starting and stopping the companion. Nothing here
# installs, and nothing writes outside the temporary directory.
#
#   ./scripts/tray-smoke.sh                    # native host
#   CDX_TRAY_WSL=1 ./scripts/tray-smoke.sh     # Windows host serving CDX in WSL
set -uo pipefail

COMPANION="${CDX_TRAY_BIN:-}"
PASS=0
FAIL=0

check() {
  local name="$1" outcome="$2" detail="${3:-}"
  if [ "$outcome" = "pass" ]; then
    PASS=$((PASS + 1))
    printf '  PASS  %-38s %s\n' "$name" "$detail"
  else
    FAIL=$((FAIL + 1))
    printf '  FAIL  %-38s %s\n' "$name" "$detail"
  fi
}

# A Windows companion driven from WSL reports Windows paths, which this shell
# cannot open. Translating is the whole reason the check can run at all from the
# side where bash lives.
host_path() {
  case "$1" in
    ?:\\*|?:/*) command -v wslpath >/dev/null 2>&1 && wslpath -u "$1" || printf '%s' "$1" ;;
    *) printf '%s' "$1" ;;
  esac
}

if [ -z "$COMPANION" ]; then
  echo "Set CDX_TRAY_BIN to the companion to test." >&2
  exit 2
fi

printf 'tray smoke: %s\n' "$COMPANION"
# The shell and the companion are not always the same platform: driving a
# Windows companion from WSL is a supported arrangement, and a record that
# reported only `uname` would name the wrong tray under test.
case "$COMPANION" in
  *.exe) printf 'companion: Windows\n' ;;
  *)     printf 'companion: %s %s\n' "$(uname -s)" "$(uname -m)" ;;
esac
printf 'shell: %s %s\n' "$(uname -s)" "$(uname -m)"
printf 'transport: %s\n\n' "$([ "${CDX_TRAY_WSL:-0}" = 1 ] && echo "CDX through WSL" || echo native)"

# 1. It renders a menu at all, and names which of the three states it is in.
#    All three are legitimate outcomes on a real host, and which one you get
#    depends on the machine rather than on the code: a populated fleet, a host
#    with nothing enabled, and a CDX that cannot answer. Only a fourth,
#    unrecognised shape is a failure.
OUTPUT="$("$COMPANION" --print 2>&1)"
if printf '%s' "$OUTPUT" | grep -q "CDX ·"; then
  check "renders a menu" pass "$(printf '%s' "$OUTPUT" | head -1 | tr -d '\n')"
elif printf '%s' "$OUTPUT" | grep -q "No enabled CDX sessions"; then
  check "renders an empty fleet" pass "nothing enabled on this host"
elif printf '%s' "$OUTPUT" | grep -q "unavailable"; then
  # A named boundary is a pass for this check: the point is that it never
  # invents a figure, and "unavailable" is the honest answer when CDX is absent.
  check "names its boundary" pass "$(printf '%s' "$OUTPUT" | sed -n 2p | tr -d '\n')"
else
  check "renders a menu" fail "$(printf '%s' "$OUTPUT" | head -2 | tr '\n' ' ')"
fi

# 2. No figure may appear when nothing is known. This is the rule that survives
#    every refactor only because something checks it on a real machine, and it
#    covers both states that know nothing: an unavailable CDX and an empty fleet.
if printf '%s' "$OUTPUT" | grep -qE "unavailable|No enabled CDX sessions" \
  && printf '%s' "$OUTPUT" | grep -q "%"; then
  check "invents no quota when nothing is known" fail "a percentage appeared without a session to back it"
else
  check "invents no quota when nothing is known" pass
fi

# 3. The poll period matches the transport, which is what bounds both the idle
#    cost and the alert latency.
PERIOD="$(printf '%s' "$OUTPUT" | sed -n 's/.*next poll in \([0-9]*\)s.*/\1/p')"
case "${CDX_TRAY_WSL:-0}:${PERIOD:-none}" in
  1:60) check "poll period" pass "60s across WSL" ;;
  1:*)  check "poll period" fail "expected 60s across WSL, got ${PERIOD:-none}" ;;
  *:30) check "poll period" pass "30s native" ;;
  *:none) check "poll period" pass "polling stopped (no enabled session)" ;;
  *)    check "poll period" fail "expected 30s native, got $PERIOD" ;;
esac

# 3b. The poll cost, measured rather than assumed, because it is the one number
#     that decides whether a 60s period is affordable and it is the one that
#     changes when the transport does. Three samples: the first pays for a cold
#     WSL VM, and reporting only that would overstate the steady-state cost.
COST_MIN=999999
COST_MAX=0
for _ in 1 2 3; do
  START="$(date +%s%N 2>/dev/null || echo 0)"
  "$COMPANION" --print >/dev/null 2>&1
  END="$(date +%s%N 2>/dev/null || echo 0)"
  if [ "$START" != 0 ] && [ "$END" != 0 ]; then
    MS=$(( (END - START) / 1000000 ))
    [ "$MS" -lt "$COST_MIN" ] && COST_MIN=$MS
    [ "$MS" -gt "$COST_MAX" ] && COST_MAX=$MS
  fi
done
if [ "$COST_MAX" -eq 0 ]; then
  check "poll cost" fail "no nanosecond clock on this host"
elif [ -n "$PERIOD" ]; then
  # Worst-case alert latency is one full period plus the poll that ends it: a
  # change landing just after a fetch waits for the next one.
  check "poll cost" pass "${COST_MIN}-${COST_MAX}ms, so alert latency <= $((PERIOD + COST_MAX / 1000 + 1))s"
else
  check "poll cost" pass "${COST_MIN}-${COST_MAX}ms, no period to bound (polling stopped)"
fi

# 4. A second companion must refuse rather than draw a second icon.
"$COMPANION" >/dev/null 2>&1 &
FIRST=$!
sleep 2
SECOND="$("$COMPANION" 2>&1)"
SECOND_CODE=$?
kill "$FIRST" 2>/dev/null
wait "$FIRST" 2>/dev/null
if [ "$SECOND_CODE" -eq 3 ] && printf '%s' "$SECOND" | grep -q "already running"; then
  check "refuses a second instance" pass "exit 3, names the pid"
else
  check "refuses a second instance" fail "exit $SECOND_CODE: $(printf '%s' "$SECOND" | head -1)"
fi

# 5. A killed companion leaves its lock behind — Drop does not run on a signal —
#    and the next launch must reclaim it. That recovery is the point: a lock
#    that outlived a crash without being reclaimable would leave the tray
#    permanently unstartable, which is worse than the duplicate it prevents.
#    The companion is asked where its lock is rather than told: the rule is
#    TMPDIR here and LOCALAPPDATA on Windows, and a script that reimplemented it
#    would look in the wrong place on the platform this check exists for.
LOCK="$("$COMPANION" --lock-path 2>/dev/null | tr -d '\r')"
if [ -z "$LOCK" ]; then
  check "reclaims a stale lock" fail "the companion did not report a lock path"
  printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
  exit 1
fi
LOCK="$(host_path "$LOCK")"
mkdir -p "$(dirname "$LOCK")"
printf '4000000000' > "$LOCK"
"$COMPANION" >/dev/null 2>&1 &
THIRD=$!
sleep 2
RECLAIMED="$(tr -d '\r' < "$LOCK" 2>/dev/null)"
kill "$THIRD" 2>/dev/null
wait "$THIRD" 2>/dev/null
if [ "$RECLAIMED" = "4000000000" ] || [ -z "$RECLAIMED" ]; then
  check "reclaims a stale lock" fail "a dead pid still owns the lock"
else
  check "reclaims a stale lock" pass "took over from a dead pid, now $RECLAIMED"
fi
rm -f "$LOCK"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
