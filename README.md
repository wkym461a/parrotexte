# Parrotexte

ボイスメッセージを文字起こしして返すDiscord Bot。

## 想定環境

- Docker on UGREEN NASync (DH4300 Plus)

## 使い方

1. Dockerアプリ＞プロジェクト＞Compose設定（`docker-compose.yml`）に以下を記述する。
2. `.env`ファイルを新規作成し、環境変数`DISCORD_BOT_TOKEN`として[Discord Developer Portal](https://discord.com/developers/home)から取得したBotトークンを記載する。
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
            # NAS上の実際のObsidian保管庫（ライフログ用フォルダ）のパスを、コンテナの /obsidian に繋ぐ
            - /volume1/workspace/life/log:/obsidian
        depends_on:
            - ollama
    
    # ローカルAIのOllamaコンテナ
    ollama:
        image: ollama/ollama:latest
        container_name: ollama
        restart: always
        volumes:
            - ./ollama_data:/root/.ollama  # モデルデータをNASに永続化
        # モデルの自動ダウンロードの仕組みを記述
        entrypoint: >
            /bin/sh -c "
            ollama serve & 
            sleep 5; 
            echo 'Checking and pulling model...'; 
            ollama pull gemma2:2b; 
            tail -f /dev/null
            "
```

## 関連リンク

- [wkym461a/parrotexte | Docker Hub](https://hub.docker.com/repository/docker/wkym461a/parrotexte)
