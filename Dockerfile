FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    ffmpeg \
    wget \
    bash \
    nodejs \
    npm \
    ca-certificates \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["bash","-c","flask run -h 0.0.0.0 -p 5000 & python3 main.py"]
