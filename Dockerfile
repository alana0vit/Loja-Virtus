# Uma única imagem para os 4 serviços + gerador de carga.
# Cada contêiner escolhe o serviço pelo comando: python -m app.run <servico>
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
