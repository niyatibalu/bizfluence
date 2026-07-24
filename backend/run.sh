#!/usr/bin/env bash
cd "$(dirname "$0")"
export PYTHONPATH=.
exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
