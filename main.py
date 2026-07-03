import os
import discord
from discord.ext import commands

# 1. Botのインテント（権限）を設定
# メッセージの内容を読み取るために message_content が必須です
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name} (ID: {bot.user.id})")
    print("------")

@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視する
    if message.author == bot.user:
        return

    # メッセージに添付ファイルがあり、それがボイスメッセージかどうかを判定
    if message.attachments:
        # 添付ファイルがボイスメッセージかどうかを判定
        for attachment in message.attachments:
            if attachment.is_voice_message():
                # テスト用の固定メッセージを返信（ここに将来Whisperの処理が入ります）
                await message.reply("ボイスメッセージを受け取ったよ！文字起こし機能は現在準備中です。")
                break

    # この記述を入れておくことで、将来的に !help などのコマンドを追加した際も正常に動作します
    await bot.process_commands(message)

# 2. 環境変数からトークンを読み込んで起動
# Dockerコンテナ側（環境変数）からトークンを渡せるようにしておきます
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー: 環境変数 'DISCORD_BOT_TOKEN' が設定されていません。")