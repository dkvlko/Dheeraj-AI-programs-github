#!/usr/bin/env bash

set -u
set -o pipefail

# ============================================================
# Gemini NHCN fetcher
# Ubuntu Noble
# Refresh interval: controlled by cron
# ============================================================

SCRIPT_DIR="/home/dkvlko/Dheeraj-AI-programs-github/liv_code"

OUTPUT_DIR="/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS"

OUTPUT_FILE="${OUTPUT_DIR}/CalAndHolidays/gemini_nhcn.json"

LOG_FILE="${OUTPUT_DIR}/gemini_nhcn.log"

ENV_FILE="/home/dkvlko/.config/gemini.env"

MODEL="gemini-3.6-flash"

API_URL="https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent"

# ------------------------------------------------------------
# Functions
# ------------------------------------------------------------

log()
{
    printf '[%s] %s\n' \
        "$(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S %Z')" \
        "$*" >> "$LOG_FILE"
}

fail()
{
    log "ERROR: $*"
    exit 1
}

# ------------------------------------------------------------
# Basic checks
# ------------------------------------------------------------

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
    fail "Gemini environment file not found: $ENV_FILE"
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    fail "GEMINI_API_KEY is not set"
fi

if ! command -v curl >/dev/null 2>&1; then
    fail "curl is not installed"
fi

if ! command -v jq >/dev/null 2>&1; then
    fail "jq is not installed"
fi

# ------------------------------------------------------------
# Date/time
# ------------------------------------------------------------

TODAY_ISO="$(TZ=Asia/Kolkata date '+%Y-%m-%d')"

DATE_TEXT="$(TZ=Asia/Kolkata date '+%d %B %Y')"

GENERATED_TIMESTAMP="$(TZ=Asia/Kolkata date '+%s')"

GENERATED_AT="$(TZ=Asia/Kolkata date --iso-8601=seconds)"

log "Starting Gemini NHCN fetch"
log "Date: ${DATE_TEXT}"
log "Model: ${MODEL}"

# ------------------------------------------------------------
# Prompt
# ------------------------------------------------------------

read -r -d '' PROMPT <<EOF || true
Today is ${DATE_TEXT}.

The location is Lucknow, Uttar Pradesh, India.

Using Google Search grounding, provide current and
accurate information for the following three sections.

SECTION 1 — HOLIDAYS

List Indian, Uttar Pradesh, and locally relevant public/
government holidays for every calendar date from today
through the next 9 days, giving exactly 10 calendar days
including today.

Do not invent holidays.

If there is no relevant holiday on a date, do not create
an entry for that date.

For each holiday provide:
- date
- holiday name
- short reason

SECTION 2 — TOP 5 INDIAN HEADLINES

Find the 5 most significant current Indian news stories
available as of now.

Prefer reliable established news sources.

For each provide:
- headline
- source

SECTION 3 — TOP 5 INTERNATIONAL HEADLINES

Find the 5 most significant current international news
stories available as of now.

Prefer reliable established international news sources.

For each provide:
- headline
- source

IMPORTANT:

Return ONLY valid JSON.

Do not use Markdown.
Do not use \`\`\`json.
Do not add explanations before or after the JSON.

Use exactly this structure:

{
    "holidays": [
        {
            "date": "DD Month YYYY",
            "name": "Holiday name",
            "reason": "Short reason"
        }
    ],

    "indian_headlines": [
        {
            "title": "Headline",
            "source": "Source"
        }
    ],

    "international_headlines": [
        {
            "title": "Headline",
            "source": "Source"
        }
    ]
}
EOF

# ------------------------------------------------------------
# Build Gemini request
# ------------------------------------------------------------

REQUEST_FILE="$(mktemp)"

RESPONSE_FILE="$(mktemp)"

MODEL_JSON_FILE="$(mktemp)"

FINAL_TEMP_FILE="$(mktemp "${OUTPUT_DIR}/.gemini_nhcn.XXXXXX")"

cleanup()
{
    rm -f \
        "$REQUEST_FILE" \
        "$RESPONSE_FILE" \
        "$MODEL_JSON_FILE" \
        "$FINAL_TEMP_FILE"
}

trap cleanup EXIT

jq -n \
    --arg prompt "$PROMPT" \
    '{
        contents: [
            {
                parts: [
                    {
                        text: $prompt
                    }
                ]
            }
        ],
        tools: [
            {
                google_search: {}
            }
        ]
    }' > "$REQUEST_FILE"

# ------------------------------------------------------------
# Call Gemini
# ------------------------------------------------------------

HTTP_STATUS="$(
    curl \
        --silent \
        --show-error \
        --connect-timeout 30 \
        --max-time 180 \
        --retry 2 \
        --retry-delay 5 \
        -X POST \
        "$API_URL" \
        -H "x-goog-api-key: ${GEMINI_API_KEY}" \
        -H "Content-Type: application/json" \
        --data-binary "@${REQUEST_FILE}" \
        -o "$RESPONSE_FILE" \
        -w '%{http_code}'
)"

# Error Handling
#
if [[ "$HTTP_STATUS" != "200" ]]; then

    # Extract Gemini's actual error message.
    GEMINI_ERROR_MESSAGE="$(
        jq -r '
            .error.message //
            "Unknown Gemini API error"
        ' "$RESPONSE_FILE" 2>/dev/null
    )"

    GEMINI_ERROR_STATUS="$(
        jq -r '
            .error.status //
            "UNKNOWN"
        ' "$RESPONSE_FILE" 2>/dev/null
    )"

    GEMINI_ERROR_CODE="$(
        jq -r '
            .error.code //
            "UNKNOWN"
        ' "$RESPONSE_FILE" 2>/dev/null
    )"

    # Safety fallback.
    if [[ -z "$GEMINI_ERROR_MESSAGE" ||
          "$GEMINI_ERROR_MESSAGE" == "null" ]]; then
        GEMINI_ERROR_MESSAGE="Unknown Gemini API error"
    fi

    ERROR_TITLE="Gemini API Error"

    ERROR_SOURCE="Google Gemini API — HTTP ${GEMINI_ERROR_CODE} ${GEMINI_ERROR_STATUS}"

    ERROR_REASON="HTTP ${GEMINI_ERROR_CODE} ${GEMINI_ERROR_STATUS}: ${GEMINI_ERROR_MESSAGE}"

    log "ERROR: Gemini HTTP status ${HTTP_STATUS}"
    log "Gemini error status: ${GEMINI_ERROR_STATUS}"
    log "Gemini error message: ${GEMINI_ERROR_MESSAGE}"

    # --------------------------------------------------------
    # Return the Gemini error in exactly the same JSON
    # structure expected by the application.
    # --------------------------------------------------------

    jq -n \
        --arg date "$TODAY_ISO" \
        --argjson timestamp "$GENERATED_TIMESTAMP" \
        --arg generated_at "$GENERATED_AT" \
        --arg error_title "$ERROR_TITLE" \
        --arg error_source "$ERROR_SOURCE" \
        --arg error_reason "$ERROR_REASON" \
        '{
            date: $date,
            generated_timestamp: $timestamp,
            generated_at: $generated_at,
            data: {
                holidays: [
                    {
                        date: ($date | strptime("%Y-%m-%d") | strftime("%d %B %Y")),
                        name: $error_title,
                        reason: $error_reason
                    }
                ],

                indian_headlines: [
                    {
                        title: $error_title,
                        source: $error_source
                    }
                ],

                international_headlines: [
                    {
                        title: $error_title,
                        source: $error_source
                    }
                ]
            }
        }' > "$FINAL_TEMP_FILE"

    # Atomically replace the output.
    if mv -f "$FINAL_TEMP_FILE" "$OUTPUT_FILE"; then
        log "Gemini error written to ${OUTPUT_FILE}"
    else
        log "ERROR: Could not write Gemini error output"
        exit 1
    fi

    exit 0
fi
#
log "Gemini API request succeeded"

# ------------------------------------------------------------
# Extract model text
# ------------------------------------------------------------

if ! jq -e '.candidates[0].content.parts' "$RESPONSE_FILE" >/dev/null 2>&1; then
    log "ERROR: Gemini response does not contain candidate content"
    exit 1
fi

jq -r '
    .candidates[0].content.parts[]
    | select(.text != null)
    | .text
' "$RESPONSE_FILE" > "$MODEL_JSON_FILE"

if [[ ! -s "$MODEL_JSON_FILE" ]]; then
    log "ERROR: Gemini returned empty text"
    exit 1
fi

# ------------------------------------------------------------
# Clean accidental Markdown fences if Gemini ever adds them
# ------------------------------------------------------------

sed -i \
    -e '/^[[:space:]]*```json[[:space:]]*$/d' \
    -e '/^[[:space:]]*```[[:space:]]*$/d' \
    "$MODEL_JSON_FILE"

# ------------------------------------------------------------
# Validate Gemini JSON
# ------------------------------------------------------------

if ! jq empty "$MODEL_JSON_FILE" >/dev/null 2>&1; then
    log "ERROR: Gemini returned invalid JSON"
    log "Invalid Gemini output:"
    head -c 4000 "$MODEL_JSON_FILE" >> "$LOG_FILE"
    log ""
    exit 1
fi

# ------------------------------------------------------------
# Validate required structure
# ------------------------------------------------------------

if ! jq -e '
    type == "object"
    and (.holidays | type == "array")
    and (.indian_headlines | type == "array")
    and (.international_headlines | type == "array")
' "$MODEL_JSON_FILE" >/dev/null 2>&1; then

    log "ERROR: Gemini JSON has incorrect top-level structure"
    exit 1
fi

# Require exactly five Indian headlines.

INDIAN_COUNT="$(jq '.indian_headlines | length' "$MODEL_JSON_FILE")"

if [[ "$INDIAN_COUNT" != "5" ]]; then
    log "ERROR: Expected 5 Indian headlines, received ${INDIAN_COUNT}"
    exit 1
fi

# Require exactly five international headlines.

INTERNATIONAL_COUNT="$(
    jq '.international_headlines | length' "$MODEL_JSON_FILE"
)"

if [[ "$INTERNATIONAL_COUNT" != "5" ]]; then
    log "ERROR: Expected 5 international headlines, received ${INTERNATIONAL_COUNT}"
    exit 1
fi

# ------------------------------------------------------------
# Create final cache object
# ------------------------------------------------------------

if ! jq \
    --arg date "$TODAY_ISO" \
    --argjson timestamp "$GENERATED_TIMESTAMP" \
    --arg generated_at "$GENERATED_AT" \
    --slurpfile data "$MODEL_JSON_FILE" \
    '{
        date: $date,
        generated_timestamp: $timestamp,
        generated_at: $generated_at,
        data: $data[0]
    }' \
    > "$FINAL_TEMP_FILE"; then

    log "ERROR: Failed to construct final JSON"
    exit 1
fi

# ------------------------------------------------------------
# Final validation
# ------------------------------------------------------------

if ! jq empty "$FINAL_TEMP_FILE" >/dev/null 2>&1; then
    log "ERROR: Final JSON validation failed"
    exit 1
fi

# ------------------------------------------------------------
# Atomic cache replacement
#
# IMPORTANT:
# Existing valid cache is never removed until a complete,
# valid replacement has been created.
# ------------------------------------------------------------

if ! mv -f "$FINAL_TEMP_FILE" "$OUTPUT_FILE"; then
    log "ERROR: Could not replace output file"
    exit 1
fi

# ------------------------------------------------------------
# Success
# ------------------------------------------------------------

log "SUCCESS: NHCN data written to ${OUTPUT_FILE}"

log "Indian headlines: ${INDIAN_COUNT}"
log "International headlines: ${INTERNATIONAL_COUNT}"

exit 0
