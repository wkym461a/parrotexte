# Parrotexte

ボイスメッセージを文字起こしして返すDiscord Bot。

## 想定環境

- Docker on UGREEN NASync (DH4300 Plus)

## 使い方

1. `docker-compose.yml`に以下を記述する。
2. `.env`ファイルに環境変数`DISCORD_BOT_TOKEN`として、[Discord Developer Portal](https://discord.com/developers/home)から取得したBotトークンを記載する。
3. `.env`ファイルを`docker-compose.yml`と同じフォルダに配置する。
4. プロジェクトを起動する。

```docker-compose.yml
version: '3.8'

services:
  parrotexte:
    image: wkym461a/parrotexte # DockerHubイメージ
    container_name: parrotexte
    restart: always
    environment:
      - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN}
      - PYTHONUNBUFFERED=1
    volumes:
      # Whisperのモデルデータが毎回消えないように、NASのローカルにキャッシュ用マウントを作る
      - ./whisper_cache:/root/.cache/huggingface
```

## 関連リンク

- [wkym461a/parrotexte | Docker Hub](https://hub.docker.com/repository/docker/wkym461a/parrotexte)
