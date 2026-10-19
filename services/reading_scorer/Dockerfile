# Reading Scorer (PRD 15.2): CPU only. Build from the repo root:
#   docker build -f services/reading_scorer/Dockerfile .
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=True DEBIAN_FRONTEND=noninteractive PYTHONPATH=/app:/app/libs/aloai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.7.1 torchaudio==2.7.1
COPY services/reading_scorer/requirements.txt services/reading_scorer/requirements.txt
RUN pip install --no-cache-dir -r services/reading_scorer/requirements.txt
# Bake the alignment and VAD models into the image so no request downloads them.
RUN python -c "import torchaudio; torchaudio.pipelines.MMS_FA.get_model(with_star=True)" \
    && python -c "from silero_vad import load_silero_vad; load_silero_vad()"
COPY schemas schemas
COPY libs libs
COPY fixtures/ai/reading fixtures/ai/reading
COPY services/reading_scorer services/reading_scorer
CMD ["uvicorn", "services.reading_scorer.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
