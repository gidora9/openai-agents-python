FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-deploy.txt pyproject.toml README.md ./
COPY src ./src
COPY deploy ./deploy

RUN pip install --no-cache-dir -r requirements-deploy.txt

EXPOSE 8000

CMD ["uvicorn", "deploy.agent_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
