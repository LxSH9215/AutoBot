FROM python:3.10-slim
RUN apt-get update && apt-get install -y git gcc g++
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
WORKDIR /app
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
