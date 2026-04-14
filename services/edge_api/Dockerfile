FROM python:3.12-slim
WORKDIR /app
COPY services/edge_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/edge_api/ .
COPY schemas/ schemas/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
