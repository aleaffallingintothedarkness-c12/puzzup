# Local development image for PuzzUp (matches Render: Python 3.9 + Poetry 1.8.5).
FROM python:3.9-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Poetry lives in its own venv so installing PuzzUp's old pinned packages
# can't downgrade Poetry's own dependencies mid-install.
RUN python -m venv /opt/poetry \
    && /opt/poetry/bin/pip install --no-cache-dir poetry==1.8.5

# PuzzUp's packages go into a separate venv, activated for everything below.
ENV VIRTUAL_ENV=/venv \
    PATH=/venv/bin:$PATH
RUN python -m venv /venv

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN /opt/poetry/bin/poetry install --no-root --no-interaction

# Run as your WSL user (uid 1000) so files written into the hunt repo stay yours,
# and so ssh has a real user to run as.
RUN useradd -m -u 1000 app
USER app
