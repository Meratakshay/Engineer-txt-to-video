import os
import mmap
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

# Bot configuration
API_ID = 21705536  # Replace with your API ID
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token

# Initialize the Pyrogram client
app = Client("file_decryptor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def download_with_ytdlp(url, save_path):
    try:
        print(f"Downloading with yt-dlp: {url}")
        cmd = [
            'yt-dlp',
            '-o', save_path,
            '--no-check-certificate',
            '--quiet',
            '--no-warnings',
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"yt-dlp error: {result.stderr}")
            return False
        
        print(f"Download completed: {save_path}")
        return True
    except Exception as e:
        print(f"Download error: {e}")
        return False

def extract_url_and_key(full_url):
    if '*' not in full_url:
        return None, None
    
    parts = full_url.split('*', 1)
    video_url = parts[0]
    key = parts[1] if len(parts) > 1 else None
    
    if not (video_url.startswith('http://') or video_url.startswith('https://')):
        return None, None
    
    return video_url, key

def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        print("File not found!")
        return False
    
    try:
        print(f"Decrypting {file_path} with key: {key}")
        with open(file_path, "r+b") as f:
            num_bytes = min(28, os.path.getsize(file_path))
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i % len(key)])
        print("Decryption successful!")
        return True
    except Exception as e:
        print(f"Decryption error: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hi! I'm a video downloader and decryption bot.\n\n"
        "Send me a URL in this format:\n"
        "`https://example.com/video*decryptionkey`\n\n"
        "I'll download the video and decrypt it for you!"
    )

@app.on_message(filters.text & ~filters.command("start"))
async def handle_url(client: Client, message: Message):
    user_input = message.text.strip()
    video_url, decryption_key = extract_url_and_key(user_input)
    
    if not video_url or not decryption_key:
        await message.reply_text(
            "❌ Invalid format. Please use:\n"
            "`https://example.com/video*decryptionkey`"
        )
        return
    
    processing_msg = await message.reply_text("🔍 Processing your request...")
    
    try:
        temp_dir = "temp_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download with yt-dlp
        await processing_msg.edit_text("⬇️ Downloading video...")
        temp_file = os.path.join(temp_dir, "video_temp")
        
        if not download_with_ytdlp(video_url, temp_file):
            await processing_msg.edit_text("❌ Download failed. Check the URL.")
            return
        
        # Find the actual downloaded file (yt-dlp might add extension)
        downloaded_file = None
        for f in os.listdir(temp_dir):
            if f.startswith("video_temp"):
                downloaded_file = os.path.join(temp_dir, f)
                break
        
        if not downloaded_file:
            await processing_msg.edit_text("❌ Couldn't find downloaded file.")
            return
        
        # Decrypt the file
        await processing_msg.edit_text("🔓 Decrypting...")
        if not decrypt_file(downloaded_file, decryption_key):
            await processing_msg.edit_text("❌ Decryption failed. Check your key.")
            return
        
        # Prepare final filename
        ext = os.path.splitext(downloaded_file)[1] or '.mp4'
        final_path = os.path.join(temp_dir, f"decrypted{ext}")
        os.rename(downloaded_file, final_path)
        
        # Send to user
        await processing_msg.edit_text("📤 Uploading...")
        await message.reply_document(
            document=final_path,
            caption="Here's your decrypted video!",
            progress=lambda current, total: print(f"Uploaded {current}/{total} bytes")
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
        if 'processing_msg' in locals():
            await processing_msg.delete()
    
    finally:
        # Clean up
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass

print("Bot is running...")
app.run()
