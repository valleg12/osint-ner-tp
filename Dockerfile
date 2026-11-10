# Image de service de l'API OSINT-NER.
# Le modèle fine-tuné est monté au lancement (il n'est pas versionné) :
#   docker build -t osint-ner-api .
#   docker run -p 8000:8000 -v "$PWD/output/model-best:/model" osint-ner-api
FROM python:3.12-slim

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir "spacy>=3.8.14,<3.9" "fastapi>=0.115" "uvicorn[standard]>=0.30"
COPY src/ src/

ENV MODEL_PATH=/model
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
