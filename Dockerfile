FROM python:3.11-slim

WORKDIR /srv/app

# System deps for scikit-learn/numpy wheels build tooling (kept minimal;
# manylinux wheels usually avoid needing a compiler, but curl is handy for
# container healthchecks).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Runs on an unprivileged port (8080) so the container doesn't need to run
# as root just to bind it.
#
# 9998/9999 are exposed too since this same image also runs the mock
# socket backend scripts (scripts/mock_semantic_matching_backend.py,
# scripts/mock_translate_backend.py) as separate services in
# docker-compose.yml -- see that file's comments for which of those are
# temporary stand-ins to be removed once real backends are deployed.
EXPOSE 8080 9998 9999

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
