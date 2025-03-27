import os
import mmap
import requests
from pyrogram import Client, filters
from pyrogram.types import Message

# Bot configuration
API_ID = 21705536  # Replace with your API ID from https://my.telegram.org
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token from @BotFather

# Initialize the Pyrogram client
app = Client("file_decryptor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def download_file(url, save_path):
    try:
        print(f"Downloading file from: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Check for HTTP errors

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        print(f"File downloaded successfully at: {save_path}")
        return True
    except Exception as e:
        print(f"Error during download: {e}")
        return False

def extract_url_and_key(full_url):
    if '*' not in full_url:
        return None, None
    
    parts = full_url.split('*', 1)  # Split on first '*' only
    video_url = parts[0]
    key = parts[1] if len(parts) > 1 else None
    
    # Validate URL
    if not (video_url.startswith('http://') or video_url.startswith('https://')):
        return None, None
    
    return video_url, key

def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        print("Encrypted file not found!")
        return False
    
    try:
        print(f"Decrypting file: {file_path} with key: {key}")
        with open(file_path, "r+b") as f:
            num_bytes = min(28, os.path.getsize(file_path))
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i % len(key)])  # Use modulo to cycle through key
        print("Decryption completed successfully!")
        return True
    except Exception as e:
        print(f"Error during decryption: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hello! I'm a file decryption bot.\n\n"
        "Send me a URL in this format:\n"
        "`https://example.com/encrypted.mkv*mysecretkey`\n\n"
        "Where:\n"
        "- Before * is the video URL\n"
        "- After * is the decryption key"
    )

@app.on_message(filters.text & ~filters.command("start"))
async def handle_url(client: Client, message: Message):
    user_input = message.text.strip()
    
    # Extract URL and key
    video_url, decryption_key = extract_url_and_key(user_input)
    
    if not video_url or not decryption_key:
        await message.reply_text(
            "❌ Invalid format. Please use:\n"
            "`https://example.com/file.mkv*decryptionkey`"
        )
        return
    
    processing_msg = await message.reply_text("🔍 Processing your request...")
    
    try:
        # Create temp directory
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate file paths
        encrypted_path = os.path.join(temp_dir, "encrypted.tmp")
        decrypted_path = os.path.join(temp_dir, "decrypted.tmp")
        
        # Download only the video part (before *)
        await processing_msg.edit_text("⬇️ Downloading video...")
        if not download_file(video_url, encrypted_path):
            await processing_msg.edit_text("❌ Failed to download the file.")
            return
        
        # Decrypt with the key part (after *)
        await processing_msg.edit_text("🔓 Decrypting...")
        if not decrypt_file(encrypted_path, decryption_key):
            await processing_msg.edit_text("❌ Decryption failed. Check your key.")
            return
        
        # Rename file with original extension if possible
        original_filename = os.path.basename(video_url.split('?')[0].split('#')[0])
        if '.' in original_filename:
            ext = original_filename.split('.')[-1]
            final_path = os.path.join(temp_dir, f"decrypted.{ext}")
            os.rename(encrypted_path, final_path)
        else:
            final_path = encrypted_path
        
        # Send to user
        await processing_msg.edit_text("📤 Uploading...")
        await message.reply_document(
            document=final_path,
            caption="Here's your decrypted file!",
            progress=lambda current, total: print(f"Uploaded {current} of {total} bytes")
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
        if 'processing_msg' in locals():
            await processing_msg.delete()
    
    finally:
        # Clean up
        for f in [encrypted_path, decrypted_path, final_path]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except:
                pass

print("Bot is running...")
app.run()
