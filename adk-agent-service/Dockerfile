FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

CMD ["sh", "-c", "python -m uvicorn styling_app.server:app --host 0.0.0.0 --port ${PORT:-3000}"]
