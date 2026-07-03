import os
import asyncio
import discord
from discord.ext import commands
import urllib.request
from faster_whisper import WhisperModel

# Botのインテント（権限）を設定
# メッセージの内容を読み取るために message_content が必須です
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# UGREEN NASのCPU（RK3588C）に最適化したWhisperモデルの初期化
# 初回起動時に自動でモデル（small）がダウンロードされます。
# ボリュームマウントしておけば、次回以降はローカルキャッシュから爆速で読み込まれます。
print("Whisperモデルをロード中...")
model = WhisperModel(
    "small", 
    device="cpu", 
    compute_type="int8",  # メモリ消費を半分に抑え、CPUでの計算を高速化
    cpu_threads=4         # NASの高性能4コアをフルに活用
)
print("Whisperモデルのロードが完了しました。")

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name} (ID: {bot.user.id})")
    print("------")

# 文字起こし処理は重いため、非同期処理(async)の中でブロックしないように別スレッドで実行する関数
def transcribe_audio(file_path):
    segments, info = model.transcribe(file_path, beam_size=5, language="ja")
    
    # 検出されたテキストを1つの文章に結合
    full_text = ""
    for segment in segments:
        full_text += segment.text
    return full_text

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
                print(f"ボイスメッセージを検知しました。送信者: {message.author}")
                
                # ユーザーに処理中であることを伝える（リアクションや一時メッセージ）
                processing_msg = await message.reply("音声を聞き取り中... 🎧")

                try:
                    # 一時的な保存ファイル名を設定
                    local_filename = f"temp_{attachment.id}.ogg"
                    
                    # 1. 音声ファイルをNASのローカルにダウンロード
                    # ※ urllib.request は同期処理なので、ブロックを防ぐためにスレッドプールで動かすのが理想ですが、
                    # 今回は数MB程度なのでシンプルに記述しています。
                    urllib.request.urlretrieve(attachment.url, local_filename)
                    print(f"ファイルをダウンロードしました: {local_filename}")

                    # 2. Whisperによる文字起こしの実行
                    # 重いCPU処理でBot全体の動きが止まらないよう、asyncio.to_thread を使用
                    loop = asyncio.get_running_loop()
                    transcribed_text = await loop.run_in_executor(None, transcribe_audio, local_filename)

                    # 3. 結果を返信
                    if transcribed_text.strip():
                        reply_text = f"**📝 文字起こし結果:**\n{transcribed_text}"
                    else:
                        reply_text = "⚠️ 音声は検知できましたが、文字に変換できませんでした。（無言、または雑音のみの可能性があります）"
                    
                    await processing_msg.edit(content=reply_text)

                except Exception as e:
                    print(f"エラーが発生しました: {e}")
                    await processing_msg.edit(content="❌ 文字起こし中にエラーが発生しました。")
                
                finally:
                    # サーバーの容量を圧迫しないよう、処理が終わったら一時ファイルを削除
                    if os.path.exists(local_filename):
                        os.remove(local_filename)
                        print(f"一時ファイルを削除しました: {local_filename}")


    # この記述を入れておくことで、将来的に !help などのコマンドを追加した際も正常に動作します
    await bot.process_commands(message)

# 環境変数からトークンを読み込んで起動
# Dockerコンテナ側（環境変数）からトークンを渡せるようにしておきます
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー: 環境変数 'DISCORD_BOT_TOKEN' が設定されていません。")