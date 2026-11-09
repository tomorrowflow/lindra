FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY lindra ./lindra
RUN pip install --no-cache-dir . \
    && useradd --system --uid 10001 lindra \
    && mkdir /data \
    && chown lindra /data

ENV LINDRA_DATA_DIR=/data
USER lindra
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "lindra.app:app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
