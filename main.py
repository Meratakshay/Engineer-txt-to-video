import os
import mmap
import requests
from pyrogram import Client, filters
from pyrogram.types import Message
from typing import Optional

# Configuration
class Config:
    API_ID: str = "21705536"  # Replace with your actual API ID
    API_HASH: str = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your actual API hash
    BOT_TOKEN: str = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your actual bot token
    DOWNLOAD_DIR: str = os.path.join(os.getcwd(), "downloads")
    MAX_KEY_LENGTH: int = 50  # Prevent excessively long keys
    MAX_FILE_SIZE: int = 2000 * 1024 * 1024  # 2GB limit for downloads


# Ensure download directory exists
os.makedirs(Config.DOWNLOAD_DIR, exist_ok=True)

# Initialize the bot
bot = Client(
    "video_downloader_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)


def extract_key_from_url(url: str) -> Optional[str]:
    """Extract decryption key from URL if present."""
    if '*' not in url:
        return None
    
    parts = url.split('*')
    if len(parts) != 2:
        return None
    
    key = parts[-1].strip()
    if not key or len(key) > Config.MAX_KEY_LENGTH:
        return None
    
    return key


def download_file(url: str, save_path: str) -> bool:
    """Download a file from URL with proper error handling."""
    try:
        # Verify URL is valid
        if not url.startswith(('http://', 'https://')):
            return False

        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            # Check file size
            file_size = int(response.headers.get('content-length', 0))
            if file_size > Config.MAX_FILE_SIZE:
                return False
                
            # Download file
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        print(f"Download error: {str(e)}")
        return False


def decrypt_file(file_path: str, key: str) -> bool:
    """Decrypt file using XOR operation with the provided key."""
    if not os.path.exists(file_path):
        return False

    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False

        # Limit the number of bytes to decrypt (first 28 bytes as in original)
        num_bytes = min(28, file_size)
        
        with open(file_path, "r+b") as f:
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    # XOR with key characters (cycling if key is shorter than num_bytes)
                    mmapped_file[i] ^= ord(key[i % len(key)])
        return True
    except Exception as e:
        print(f"Decryption error: {str(e)}")
        return False


@bot.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command."""
    help_text = (
        "Hello! I'm a video downloader and decryption bot.\n\n"
        "Send me a video URL in the format:\n"
        "`https://example.com/video.mkv*KEY`\n\n"
        "Where KEY is the decryption key that will be applied to the first 28 bytes of the file."
    )
    await message.reply_text(help_text)


@bot.on_message(filters.text & ~filters.command)
async def handle_video_request(client: Client, message: Message):
    """Handle video download and decryption requests."""
    url = message.text.strip()
    
    # Extract key from URL
    decryption_key = extract_key_from_url(url)
    if not decryption_key:
        await message.reply_text(
            "Invalid URL format!\n"
            "Please use format: `https://example.com/video.mkv*KEY`\n"
            "Where KEY is your decryption key."
        )
        return

    # Prepare file paths
    video_url = url.split('*')[0]
    encrypted_path = os.path.join(Config.DOWNLOAD_DIR, "encrypted_temp.mkv")
    decrypted_path = os.path.join(Config.DOWNLOAD_DIR, "decrypted_video.mkv")

    # Download the file
    await message.reply_text("⏳ Downloading video...")
    if not download_file(video_url, encrypted_path):
        await message.reply_text("❌ Failed to download the file. Please check the URL and try again.")
        return

    # Decrypt the file
    await message.reply_text("🔓 Decrypting video...")
    if not decrypt_file(encrypted_path, decryption_key):
        await message.reply_text("❌ Failed to decrypt the file. Please check the key and try again.")
        os.remove(encrypted_path)  # Clean up
        return

    # Rename and send the file
    os.rename(encrypted_path, decrypted_path)
    
    try:
        await message.reply_text("✅ Success! Sending the file...")
        await client.send_document(
            chat_id=message.chat.id,
            document=decrypted_path,
            caption="Here's your decrypted video file"
        )
    except Exception as e:
        await message.reply_text(f"❌ Failed to send file: {str(e)}")
    finally:
        # Clean up
        if os.path.exists(decrypted_path):
            os.remove(decrypted_path)


if __name__ == "__main__":
    print("Bot is running...")
    bot.run()
