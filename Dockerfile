FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY requirements.txt .
# Offline option for flaky networks: put Linux wheels in vendor/wheels
# (pip download -r requirements.txt -d vendor/wheels --only-binary=:all: --platform manylinux2014_x86_64 --python-version 3.11)
COPY vendor/wheels /wheels
RUN if ls /wheels/*.whl >/dev/null 2>&1; then pip install --no-index --find-links /wheels -r requirements.txt; \
    else pip install -r requirements.txt; fi

COPY app ./app
COPY eval ./eval
COPY scripts ./scripts
COPY models ./models
COPY data ./data

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
