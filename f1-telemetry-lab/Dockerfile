FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8501
CMD ["streamlit", "run", "src/f1_telemetry_lab/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
