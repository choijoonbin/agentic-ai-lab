FROM python:3.12-slim
WORKDIR /app
COPY services/agent_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/agent_worker/ .
COPY schemas/ schemas/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
