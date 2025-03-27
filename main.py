import os
import mmap
import time
import requests
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime, timedelta

# Bot configuration
API_ID = 21705536  # Replace with your API ID
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token

# Initialize the Pyrogram client
app = Client("file_decryptor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

class DownloadManager:
    def __init__(self):
        self.download_progress = {}
        self.upload_progress = {}

    class ProgressTracker:
        def __init__(self, manager, message, operation_type):
            self.manager = manager
            self.message = message
            self.operation_type = operation_type
            self.start_time = time.time()
            self.last_update_time = time.time()
            self.last_bytes = 0
            self.speed = "0 B/s"
            self.eta = "--"
            
        def update(self, current, total):
            now = time.time()
            time_since_last_update = now - self.last_update_time
            
            # Calculate percentage
            percentage = (current / total) * 100
            
            # Calculate speed (only if enough time has passed)
            if time_since_last_update > 0.5:
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
                self.manager.download_progress[self.message.chat.id] = {
                    "percentage": percentage,
                    "speed": self.speed,
                    "eta": self.eta,
                    "current": current,
                    "total": total
                }
            else:
                self.manager.upload_progress[self.message.chat.id] = {
                    "percentage": percentage,
                    "speed": self.speed,
                    "eta": self.eta,
                    "current": current,
                    "total": total
                }

    async def download_with_ytdlp(self, url, save_path, progress_tracker):
        try:
            print(f"Attempting yt-dlp download: {url}")
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
                        parts = line.split()
                        percentage = float(parts[1].replace('%', ''))
                        size_part = parts[3].split('/')
                        current_size = float(size_part[0]) * (1024 if size_part[0][-1] == 'K' else 1048576 if size_part[0][-1] == 'M' else 1)
                        total_size = float(size_part[1]) * (1024 if size_part[1][-1] == 'K' else 1048576 if size_part[1][-1] == 'M' else 1)
                        
                        progress_tracker.update(current_size, total_size)
                        
                    except Exception as e:
                        print(f"Error parsing progress: {e}")
                        continue
            
            process.wait()
            if process.returncode == 0 and os.path.exists(save_path):
                print(f"yt-dlp download successful: {save_path}")
                return True
            return False
        except Exception as e:
            print(f"yt-dlp download error: {e}")
            return False

    async def download_with_ffmpeg(self, url, save_path, progress_tracker):
        try:
            print(f"Attempting ffmpeg download: {url}")
            cmd = [
                'ffmpeg',
                '-i', url,
                '-c', 'copy',
                '-f', 'mp4',
                save_path
            ]
            
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                if "size=" in line:
                    try:
                        parts = line.split()
                        for part in parts:
                            if part.startswith("size="):
                                current_size = int(part.split('=')[1].replace('kB', '')) * 1024
                            elif part.startswith("time="):
                                time_parts = part.split('=')[1].split(':')
                                processed_seconds = float(time_parts[0])*3600 + float(time_parts[1])*60 + float(time_parts[2])
                                total_size = current_size / (processed_seconds / 100) * 100
                                
                                progress_tracker.update(current_size, total_size)
                    except Exception as e:
                        print(f"Error parsing ffmpeg progress: {e}")
            
            process.wait()
            if process.returncode == 0 and os.path.exists(save_path):
                print(f"ffmpeg download successful: {save_path}")
                return True
            return False
        except Exception as e:
            print(f"ffmpeg download error: {e}")
            return False

    async def download_with_requests(self, url, save_path, progress_tracker):
        try:
            print(f"Attempting requests download: {url}")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                
                with open(save_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress_tracker.update(f.tell(), total_size)
            
            if os.path.exists(save_path):
                print(f"requests download successful: {save_path}")
                return True
            return False
        except Exception as e:
            print(f"requests download error: {e}")
            return False

    async def download_file(self, url, save_path, progress_msg):
        """Try multiple download methods with fallback"""
        progress_tracker = self.ProgressTracker(self, progress_msg, "download")
        self.download_progress[progress_msg.chat.id] = {
            "message": progress_msg,
            "percentage": 0,
            "speed": "0 B/s",
            "eta": "--",
            "current": 0,
            "total": 1
        }
        
        methods = [
            ("yt-dlp", self.download_with_ytdlp),
            ("ffmpeg", self.download_with_ffmpeg),
            ("requests", self.download_with_requests)
        ]
        
        for method_name, method in methods:
            await progress_msg.edit_text(f"⬇️ Trying {method_name} download...")
            if await method(url, save_path, progress_tracker):
                return True
        
        return False

    async def update_progress_message(self, chat_id, operation_type):
        progress_dict = self.download_progress if operation_type == "download" else self.upload_progress
        if chat_id not in progress_dict:
            return
        
        data = progress_dict[chat_id]
        progress_bar = "⬢" * int(data["percentage"] / 10) + "⬡" * (10 - int(data["percentage"] / 10))
        
        text = (
            f"**{'Downloading' if operation_type == 'download' else 'Uploading'}...**\n\n"
            f"{progress_bar} {data['percentage']:.1f}%\n\n"
            f"**Speed:** {data['speed']}\n"
            f"**ETA:** {data['eta']}\n"
            f"**Size:** {self.format_bytes(data['current'])} / {self.format_bytes(data['total'])}"
        )
        
        try:
            await data["message"].edit_text(text)
        except:
            pass

    def format_bytes(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def extract_url_and_key(self, full_url):
        if '*' not in full_url:
            return None, None
        
        parts = full_url.split('*', 1)
        video_url = parts[0]
        key = parts[1] if len(parts) > 1 else None
        
        if not (video_url.startswith('http://') or video_url.startswith('https://')):
            return None, None
        
        return video_url, key

    def decrypt_file(self, file_path, key):
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

# Create download manager instance
download_manager = DownloadManager()

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
    video_url, decryption_key = download_manager.extract_url_and_key(user_input)
    
    if not video_url or not decryption_key:
        await message.reply_text(
            "❌ Invalid format. Please use:\n"
            "`https://example.com/video*decryptionkey`"
        )
        return
    
    progress_msg = await message.reply_text("🔍 Starting process...")
    
    try:
        temp_dir = "temp_downloads"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download the file (trying multiple methods)
        temp_file = os.path.join(temp_dir, "video_temp")
        if not await download_manager.download_file(video_url, temp_file, progress_msg):
            await progress_msg.edit_text("❌ All download methods failed.")
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
        if not download_manager.decrypt_file(downloaded_file, decryption_key):
            await progress_msg.edit_text("❌ Decryption failed. Check your key.")
            return
        
        # Prepare final filename
        ext = os.path.splitext(downloaded_file)[1] or '.mp4'
        final_path = os.path.join(temp_dir, f"decrypted{ext}")
        os.rename(downloaded_file, final_path)
        
        # Setup upload progress
        upload_tracker = download_manager.ProgressTracker(download_manager, progress_msg, "upload")
        file_size = os.path.getsize(final_path)
        download_manager.upload_progress[message.chat.id] = {
            "message": progress_msg,
            "percentage": 0,
            "speed": "0 B/s",
            "eta": "--",
            "current": 0,
            "total": file_size
        }
        
        # Upload with progress tracking
        await progress_msg.edit_text("📤 Preparing upload...")
        
        async def upload_progress(current, total):
            upload_tracker.update(current, total)
            await download_manager.update_progress_message(message.chat.id, "upload")
        
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
        if message.chat.id in download_manager.download_progress:
            del download_manager.download_progress[message.chat.id]
        if message.chat.id in download_manager.upload_progress:
            del download_manager.upload_progress[message.chat.id]

# Start the bot
print("Bot is running...")
app.run()
