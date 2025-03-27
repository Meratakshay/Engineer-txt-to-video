import os
import mmap
import time
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

# Bot configuration
API_ID = 21705536  # Replace with your API ID
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token

# Initialize the Pyrogram client
app = Client("file_decryptor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global variables for progress tracking
download_progress = {}
upload_progress = {}

class ProgressTracker:
    def __init__(self, message, operation_type):
        self.message = message
        self.operation_type = operation_type
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_bytes = 0
        self.speed = "0 B/s"
        self.eta = "--"
        
    def update(self, current, total):
        now = time.time()
        elapsed = now - self.start_time
        time_since_last_update = now - self.last_update_time
        
        # Calculate percentage
        percentage = (current / total) * 100
        
        # Calculate speed (only if we have previous data and enough time has passed)
        if time_since_last_update > 0.5:  # Update speed every 0.5 seconds
            bytes_since_last = current - self.last_bytes
            speed_bps = bytes_since_last / time_since_last
            
            # Convert to human readable format
            for unit in ['B', 'KB', 'MB', 'GB']:
                if speed_bps < 1024:
                    self.speed = f"{speed_bps:.2f} {unit}/s"
                    break
                speed_bps /= 1024
            
            # Calculate ETA
            if speed_bps > 0:
                remaining_bytes = total - current
                eta_seconds = remaining_bytes / (bytes_since_last / time_since_last)
                self.eta = str(timedelta(seconds=int(eta_seconds)))
            
            self.last_bytes = current
            self.last_update_time = now
        
        # Update progress dictionary
        if self.operation_type == "download":
            download_progress[self.message.chat.id] = {
                "percentage": percentage,
                "speed": self.speed,
                "eta": self.eta,
                "current": current,
                "total": total
            }
        else:
            upload_progress[self.message.chat.id] = {
                "percentage": percentage,
                "speed": self.speed,
                "eta": self.eta,
                "current": current,
                "total": total
            }

def download_with_ytdlp(url, save_path, progress_tracker):
    try:
        print(f"Downloading with yt-dlp: {url}")
        cmd = [
            'yt-dlp',
            '-o', save_path,
            '--no-check-certificate',
            '--newline',
            '--no-warnings',
            url
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        
        for line in process.stdout:
            if "[download]" in line and "%" in line:
                try:
                    # Parse yt-dlp progress output
                    parts = line.split()
                    percentage = float(parts[1].replace('%', ''))
                    size_part = parts[3].split('/')
                    current_size = float(size_part[0]) * (1024 if size_part[0][-1] == 'K' else 1048576 if size_part[0][-1] == 'M' else 1)
                    total_size = float(size_part[1]) * (1024 if size_part[1][-1] == 'K' else 1048576 if size_part[1][-1] == 'M' else 1)
                    speed = parts[4]
                    eta = parts[5]
                    
                    # Update progress tracker
                    progress_tracker.update(current_size, total_size)
                    
                except Exception as e:
                    print(f"Error parsing progress: {e}")
                    continue
        
        process.wait()
        if process.returncode != 0:
            print(f"yt-dlp error: {process.returncode}")
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

async def update_progress_message(chat_id, operation_type):
    progress = download_progress if operation_type == "download" else upload_progress
    if chat_id not in progress:
        return
    
    data = progress[chat_id]
    progress_bar = "⬢" * int(data["percentage"] / 10) + "⬡" * (10 - int(data["percentage"] / 10))
    
    text = (
        f"**{'Downloading' if operation_type == 'download' else 'Uploading'}...**\n\n"
        f"{progress_bar} {data['percentage']:.1f}%\n\n"
        f"**Speed:** {data['speed']}\n"
        f"**ETA:** {data['eta']}\n"
        f"**Size:** {format_bytes(data['current'])} / {format_bytes(data['total'])}"
    )
    
    try:
        message = download_progress[chat_id]["message"] if operation_type == "download" else upload_progress[chat_id]["message"]
        await message.edit_text(text)
    except:
        pass

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

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
    
    # Create progress message
    progress_msg = await message.reply_text("🔍 Starting process...")
    
    try:
        temp_dir = "temp_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Setup download progress tracker
        download_tracker = ProgressTracker(progress_msg, "download")
        download_progress[message.chat.id] = {
            "message": progress_msg,
            "percentage": 0,
            "speed": "0 B/s",
            "eta": "--",
            "current": 0,
            "total": 1
        }
        
        # Download with yt-dlp
        await progress_msg.edit_text("⬇️ Preparing download...")
        temp_file = os.path.join(temp_dir, "video_temp")
        
        if not download_with_ytdlp(video_url, temp_file, download_tracker):
            await progress_msg.edit_text("❌ Download failed. Check the URL.")
            return
        
        # Find the actual downloaded file
        downloaded_file = None
        for f in os.listdir(temp_dir):
            if f.startswith("video_temp"):
                downloaded_file = os.path.join(temp_dir, f)
                break
        
        if not downloaded_file:
            await progress_msg.edit_text("❌ Couldn't find downloaded file.")
            return
        
        # Decrypt the file
        await progress_msg.edit_text("🔓 Decrypting...")
        if not decrypt_file(downloaded_file, decryption_key):
            await progress_msg.edit_text("❌ Decryption failed. Check your key.")
            return
        
        # Prepare final filename
        ext = os.path.splitext(downloaded_file)[1] or '.mp4'
        final_path = os.path.join(temp_dir, f"decrypted{ext}")
        os.rename(downloaded_file, final_path)
        
        # Setup upload progress tracker
        upload_tracker = ProgressTracker(progress_msg, "upload")
        file_size = os.path.getsize(final_path)
        upload_progress[message.chat.id] = {
            "message": progress_msg,
            "percentage": 0,
            "speed": "0 B/s",
            "eta": "--",
            "current": 0,
            "total": file_size
        }
        
        # Send to user with progress tracking
        await progress_msg.edit_text("📤 Preparing upload...")
        
        async def upload_progress(current, total):
            upload_tracker.update(current, total)
            await update_progress_message(message.chat.id, "upload")
        
        await message.reply_document(
            document=final_path,
            caption="Here's your decrypted video!",
            progress=upload_progress
        )
        
        await progress_msg.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
        if 'progress_msg' in locals():
            await progress_msg.delete()
    
    finally:
        # Clean up
        for f in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
        # Remove progress trackers
        if message.chat.id in download_progress:
            del download_progress[message.chat.id]
        if message.chat.id in upload_progress:
            del upload_progress[message.chat.id]

# Start the bot
print("Bot is running...")
app.run()
