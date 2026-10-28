# Backend: FastAPI + vention libraries (which require Python 3.10 exactly).
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Keep the SQLite database on the /data volume (see docker-compose.yml).
    GANTRY_DB_URL=sqlite:////data/gantry.db

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY robot_sim.py ./
COPY app ./app

RUN mkdir -p /data
VOLUME /data
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
