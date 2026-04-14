FROM python:3.12-slim
WORKDIR /app
COPY services/control_plane/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/control_plane/ .
COPY schemas/ schemas/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
