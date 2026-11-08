FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY harness ./harness
COPY tests ./tests
COPY .flake8 ./.flake8
RUN pip install ".[dev]"

# Run as an unprivileged user. Combined with a read-only root filesystem
# (see docker-compose.yml) the agent cannot change the harness itself.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin agent
USER 10001

ENTRYPOINT ["python", "-m", "harness"]
CMD ["--help"]
