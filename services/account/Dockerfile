# Account and Payments service. Build from the repo root:
#   docker build -f services/account/Dockerfile .
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/libs/aloai
WORKDIR /app
COPY services/account/requirements.txt services/account/requirements.txt
RUN pip install --no-cache-dir -r services/account/requirements.txt
COPY schemas schemas
COPY libs libs
COPY services/account services/account
RUN useradd --no-create-home --shell /usr/sbin/nologin account
USER account
CMD ["uvicorn", "services.account.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
