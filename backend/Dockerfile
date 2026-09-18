FROM python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
COPY --from=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
# OCR de PDFs escaneados: binário Tesseract com pacote de língua portuguesa
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
ENV PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 govintel && useradd --uid 10001 --gid govintel --create-home govintel \
    && mkdir -p /var/lib/govintel/uploads /var/lib/govintel/huggingface \
    && chown -R govintel:govintel /app /var/lib/govintel
COPY --chown=govintel:govintel . .
USER govintel
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60"]
