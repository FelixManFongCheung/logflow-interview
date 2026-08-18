#!/bin/bash
set -e

if [ -f ".env.development" ]; then
    set -a
    # shellcheck disable=SC1091
    source ".env.development"
    set +a
elif [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source ".env"
    set +a
fi

if [ -z "${OPENAI_API_KEY}" ]; then
    echo "ERROR: OPENAI_API_KEY is required"
    exit 1
fi

exec "$@"
