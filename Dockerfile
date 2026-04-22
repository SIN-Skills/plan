FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml README.md SKILL.md BEST_PRACTICES.md LICENSE ./
COPY src ./src
COPY templates ./templates
RUN pip install --no-cache-dir build hatchling && python -m build

FROM python:3.11-slim
WORKDIR /app
RUN useradd --create-home --shell /usr/sbin/nologin plan
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
USER plan
ENTRYPOINT ["opencode-plan"]
