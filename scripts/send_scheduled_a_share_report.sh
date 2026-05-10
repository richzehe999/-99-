#!/bin/zsh
set -euo pipefail

REPORT_KIND="${1:-}"
PROJECT_ROOT="/Users/wuzehe/Documents/New project"
SECRET_FILE="$PROJECT_ROOT/local_secrets/gmail_app_password.txt"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/email-dispatch.log"
EMAIL_PREVIEW="$LOG_DIR/latest-$REPORT_KIND-email-preview.html"

mkdir -p "$LOG_DIR"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

trap 'rc=$?; log "ERROR send $REPORT_KIND failed with exit code $rc"; exit $rc' ERR

if [[ "$REPORT_KIND" != "premarket" && "$REPORT_KIND" != "aftermarket" ]]; then
  log "ERROR invalid report kind: $REPORT_KIND"
  exit 2
fi

if [[ ! -s "$SECRET_FILE" ]]; then
  log "ERROR missing Gmail app password file: $SECRET_FILE"
  exit 3
fi

export SMTP_USER="rich.zehe@gmail.com"
export SMTP_PASSWORD="$(cat "$SECRET_FILE")"
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORTS="465,587"
export A_SHARE_REPORT_TO="240575148@qq.com"

case "$REPORT_KIND" in
  premarket)
    MODE="premarket"
    ;;
  aftermarket)
    MODE="aftermarket"
    ;;
esac

cd "$PROJECT_ROOT"

python3 "$PROJECT_ROOT/scripts/cloud_a_share_radar_email.py" \
  --mode "$MODE" \
  --output-html "$EMAIL_PREVIEW" \
  --send

log "OK sent $REPORT_KIND report to $A_SHARE_REPORT_TO"
