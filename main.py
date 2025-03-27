import os
import mmap
import requests
from pyrogram import Client, filters

# Telegram API Credentials (Replace with your actual credentials)
API_ID = "21705536"
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"

# Initialize the bot
bot = Client("video_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Directory for storing files
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)


# Function to extract decryption key from the URL
def extract_key_from_url(url):
    if '*' in url:
        return url.split('*')[-1]  # Extract the part after '*'
    return None


# Function to download the video file
def download_file(url, save_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Check for HTTP errors

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
        return True
    except Exception as e:
        print(f"Download error: {e}")
        return False


# Function to decrypt the file using XOR
def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        return False

    try:
        num_bytes = min(28, os.path.getsize(file_path))
        with open(file_path, "r+b") as f:
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i]) if i < len(key) else i
        return True
    except Exception as e:
        print(f"Decryption error: {e}")
        return False


# Command: /start
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Hello! Send me a video URL in the format:\n`https://example.com/video.mkv*KEY`")


# Handle messages containing URLs
@bot.on_message(filters.text & ~filters.command)
async def handle_message(client, message):
    url = message.text.strip()

    # Extract key from URL
    decryption_key = extract_key_from_url(url)
    if not decryption_key:
        await message.reply_text("Invalid URL format! Make sure it contains '*' followed by the key.")
        return

    # Define file paths
    video_url = url.split('*')[0]
    encrypted_file_path = os.path.join(DOWNLOAD_DIR, "encrypted_video.mkv")
    decrypted_file_path = os.path.join(DOWNLOAD_DIR, "decrypted_video.mkv")

    await message.reply_text("Downloading video... Please wait.")
    if not download_file(video_url, encrypted_file_path):
        await message.reply_text("Failed to download the file.")
        return

    await message.reply_text("Decrypting video...")
    if not decrypt_file(encrypted_file_path, decryption_key):
        await message.reply_text("Failed to decrypt the file.")
        return

    os.rename(encrypted_file_path, decrypted_file_path)  # Rename the decrypted file

    await message.reply_text("Decryption completed! Sending the file...")
    await client.send_document(message.chat.id, decrypted_file_path)

    # Cleanup
    os.remove(decrypted_file_path)


# Start the bot
if __name__ == "__main__":
    bot.run()

