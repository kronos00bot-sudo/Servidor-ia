FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./skills/whatsapp

ENV PYTHONPATH=/app
ENV MACHINE_TYPE=um890
ENV WHATSAPP_WEBHOOK_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "skills.whatsapp.webhook.endpoint"]
