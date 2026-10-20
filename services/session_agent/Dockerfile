# Session Agent (LiveKit Agents worker). Built from the repo root:
#   docker build -f services/session_agent/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY services/session_agent/requirements.txt services/session_agent/requirements.txt
RUN pip install --no-cache-dir -r services/session_agent/requirements.txt

COPY services/session_agent services/session_agent
# Bank passages for local runs (BANK_DIR); in the cloud they come from Firestore.
COPY fixtures/contracts fixtures/contracts

RUN useradd --create-home agent && chown -R agent /app
USER agent

CMD ["python", "-m", "services.session_agent.main", "start"]
