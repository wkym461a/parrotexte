import os
import asyncio
import datetime
import discord
from discord.ext import commands
import urllib.request
from faster_whisper import WhisperModel
import requests
import json

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

# ローカルAI「ollama」に文字起こしした文章のタイトルを考えてもらう処理
# docker-compose内の別コンテナで「ollama」が立っている前提
def generate_title_local(text):
    # docker-compose内のサービス名「ollama」をホスト名として通信できます
    ollama_url = "http://ollama:11434/v1/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }
    
    prompt = f"""
以下のテキストは、Discordのボイスメッセージを文字起こししたものです。
この内容を分析し、全体のトピックがひと目でわかる短いタイトルを出力してください。
※タイトルのテキストだけを出力してください。他の文章は不要です。

【文字起こしテキスト】
{text}
"""
    # Ollamaに送るデータ
    payload = {
        "model": "gemma2:2b",  # 事前にダウンロードしたモデル名
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(ollama_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"] or "要約の生成に失敗しました。"
    except Exception as e:
        print(f"Ollamaとの通信エラー: {e}")
        return "❌ ローカルAIが応答しませんでした。"

# 機能：Obsidianへの保存を実行するボタンの定義
class ObsidianSaveView(discord.ui.View):
    def __init__(self, title, text):
        super().__init__(timeout=None) # タイムアウトなし（いつでも押せる）
        self.title_str = title
        self.text_str = text

    # 「ライフログに保存」ボタン
    @discord.ui.button(label="ライフログに保存", style=discord.ButtonStyle.success, emoji="📝", custom_id="save_to_obsidian")
    async def save_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 保存先フォルダの確認（docker-composeでマウントしたパス）
        obsidian_dir = "/obsidian"
        
        if not os.path.exists(obsidian_dir):
            await interaction.response.send_message("❌ NAS上のObsidianフォルダが見つかりません。設定を確認してください。", ephemeral=True)
            return

        # 2. 今日の日付のMarkdownファイル名を作成
        now_time = datetime.datetime.now().strftime(r"%Y%m%d-%H%M%s")
        file_name = f"{now_time}_{self.title_str}.md"
        file_path = os.path.join(obsidian_dir, file_name)

        try:
            # ファイルが存在しなければ新規作成、あれば末尾に追記('a')
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(self.text_str)
            
            # ボタンを無効化（グレーアウト）して二重押しを防止
            button.disabled = True
            button.label = "ライフログに保存しました"
            await interaction.response.edit_message(view=self)
            
            # 押した本人にだけ見える完了通知
            await interaction.followup.send(f"✅ `{file_name}` にライフログを追加しました！", ephemeral=True)

        except Exception as e:
            print(f"Obsidian保存エラー: {e}")
            await interaction.response.send_message(f"❌ 保存中にエラーが発生しました: {e}", ephemeral=True)

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
                    # ※ urllib.request は同期処理なので、ブロックを防ぐためにスレッドプールで動かすのが理想ですが、今回は数MB程度なのでシンプルに記述しています。

                    # ブラウザ（Chrome）からのアクセスに見せかけるための設定を追加
                    req = urllib.request.Request(
                        attachment.url, 
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                    )
                    # ヘッダー情報を持たせて安全にダウンロードを実行
                    with urllib.request.urlopen(req) as response, open(local_filename, 'wb') as out_file:
                        out_file.write(response.read())
                    print(f"ファイルをダウンロードしました: {local_filename}")

                    # 2. Whisperによる文字起こしの実行
                    # 重いCPU処理でBot全体の動きが止まらないよう、asyncio.to_thread を使用
                    loop = asyncio.get_running_loop()
                    transcribed_text = await loop.run_in_executor(None, transcribe_audio, local_filename)

                    # 3. 結果を返信
                    if transcribed_text.strip():
                        loop = asyncio.get_running_loop()
                        transcribed_title = await loop.run_in_executor(None, generate_title_local, transcribed_text)
                        transcribed_title = transcribed_title.strip()
                        reply_text = f"**📝 文字起こし結果:**\n\tタイトル:{transcribed_title}\n\t本文:{transcribed_text}"

                        # 💡 ボタン付きのビューを作成
                        # 引数として、後でMarkdownに書き込みたいデータをセットして渡します
                        view = ObsidianSaveView(
                            title=transcribed_title,
                            text=transcribed_text,
                        )
                        await processing_msg.edit(content=reply_text,view=view)
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