# Core (Passage Generator, Grader, Reading Coach). Build from the repo root:
#   docker build -f services/core/Dockerfile .
# The book job runs this image with `python -m services.core.books.reembed`.
# Recorded AI responses (fixtures/ai) are not copied: AI_MODE=fixtures is refused when hosted.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/libs/aloai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
# The spaCy model is a wheel fetched from GitHub, so this layer needs network access.
COPY services/core/requirements.txt services/core/requirements.txt
RUN pip install --no-cache-dir -r services/core/requirements.txt
COPY schemas schemas
COPY libs libs
COPY services/core services/core
RUN useradd --no-create-home --shell /usr/sbin/nologin core
USER core
CMD ["uvicorn", "services.core.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
