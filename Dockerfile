# A self-hosted scheduler for WLED lights.
#
# Single image: serves the JSON API (and, once built, the HTML pages)
# and runs the background scheduler loop in the same process. No
# separate worker or task queue needed at this project's scale.

FROM python:3.11-slim

WORKDIR /app

# Dependency metadata copied first so Docker's layer cache only
# reinstalls dependencies when they actually change, not on every
# source code edit.
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Deliberately running as root rather than adding a non-root user and
# the bind-mount permission complexity that comes with it (chown-ing
# a host directory to match a container UID). For this project's
# audience and threat model, a single-purpose container on a home
# LAN, that tradeoff favors the "simplest possible setup" decision
# made earlier over hardening that mainly adds friction here.

EXPOSE 8000

# Hardcodes port 8000 rather than reading $PORT, since Docker
# HEALTHCHECK doesn't expand shell variables in exec form. If PORT is
# overridden, update this line to match.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
