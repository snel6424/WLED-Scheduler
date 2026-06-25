#!/bin/sh
# Migrate, then serve. Always in that order.
#
# This is the one place tying together two things that both have to
# be true before the app should accept a single request: the database
# schema must be at the latest Alembic revision, and only after that
# should uvicorn start, or the scheduler loop start firing schedules
# against a schema it doesn't actually match.
set -e

alembic upgrade head

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
