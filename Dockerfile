FROM python:3.11.11-slim

# 音声処理に必要なffmpegと、ビルド用のツールをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードのコピー
COPY . .

# Botの起動
CMD ["python", "main.py"]