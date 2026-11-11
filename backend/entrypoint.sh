#!/bin/sh
# Run database migrations every time the container starts, then hand off to
# the command defined by CMD (uvicorn).  Using `exec` replaces this shell
# process so uvicorn becomes PID 1 and receives Docker stop signals correctly.
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting server..."
exec "$@"
