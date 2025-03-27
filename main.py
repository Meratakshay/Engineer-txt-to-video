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

# Function to download a file from a given URL
def download_file(url, save_path):
    try:
        print(f"Downloading file from: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Check for HTTP errors

        # Save the downloaded file
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
        print(f"File downloaded successfully at: {save_path}")
    except Exception as e:
        print(f"Error during download: {e}")
        return False
    return True

# Function to extract the decryption key from the URL
def extract_key_from_url(url):
    if '*' in url:
        return url.split('*')[-1]  # Extracts the part after '*'
    else:
        print("No key found in the URL!")
        return None

# Function to decrypt a file using XOR
def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        print("Encrypted file not found!")
        return False
    try:
        print(f"Decrypting file: {file_path}")
        with open(file_path, "r+b") as f:
            num_bytes = min(28, os.path.getsize(file_path))
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i]) if i < len(key) else i
        print("Decryption completed successfully!")
    except Exception as e:
        print(f"Error during decryption: {e}")
        return False
    return True

# Handler for the /start command
@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hello! I'm a file decryption bot.\n\n"
        "Send me a URL containing an encrypted file with the decryption key after a '*' character.\n\n"
        "Example: `https://example.com/encrypted.mkv*mysecretkey`"
    )

# Handler for all text messages (to process URLs)
@app.on_message(filters.text & ~filters.command("start"))
async def handle_url(client: Client, message: Message):
    # Check if the message contains a URL
    if not any(proto in message.text for proto in ["http://", "https://"]):
        await message.reply_text("Please send a valid HTTP/HTTPS URL.")
        return
    
    # Extract the decryption key from the URL
    decryption_key = extract_key_from_url(message.text)
    if not decryption_key:
        await message.reply_text("No decryption key found in the URL! Please include the key after a '*' character.")
        return
    
    # Inform user we're processing
    processing_msg = await message.reply_text("🔍 Processing your request...")
    
    try:
        # Create a temporary directory if it doesn't exist
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate file paths
        encrypted_file_path = os.path.join(temp_dir, "encrypted_file.tmp")
        decrypted_file_path = os.path.join(temp_dir, "decrypted_file.tmp")
        
        # Step 1: Download the encrypted file
        await processing_msg.edit_text("⬇️ Downloading file...")
        download_url = message.text.split('*')[0]  # URL without the key
        if not download_file(download_url, encrypted_file_path):
            await processing_msg.edit_text("❌ Failed to download the file. Please check the URL.")
            return
        
        # Step 2: Decrypt the file
        await processing_msg.edit_text("🔓 Decrypting file...")
        if not decrypt_file(encrypted_file_path, decryption_key):
            await processing_msg.edit_text("❌ Failed to decrypt the file. Invalid key or file format.")
            return
        
        # Rename the decrypted file (keeping original extension if possible)
        original_name = os.path.basename(download_url.split('?')[0])  # Remove query params
        if '.' in original_name:
            ext = original_name.split('.')[-1]
            decrypted_file_path_final = os.path.join(temp_dir, f"decrypted.{ext}")
            os.rename(encrypted_file_path, decrypted_file_path_final)
        else:
            decrypted_file_path_final = encrypted_file_path
        
        # Step 3: Send the decrypted file to the user
        await processing_msg.edit_text("📤 Uploading decrypted file...")
        await message.reply_document(
            document=decrypted_file_path_final,
            caption="Here's your decrypted file!",
            progress=lambda current, total: print(f"Uploaded {current} of {total} bytes")
        )
        
        await processing_msg.delete()
        
    except Exception as e:
        await message.reply_text(f"❌ An error occurred: {str(e)}")
        if 'processing_msg' in locals():
            await processing_msg.delete()
    
    finally:
        # Clean up temporary files
        for file in [encrypted_file_path, decrypted_file_path, decrypted_file_path_final]:
            try:
                if file and os.path.exists(file):
                    os.remove(file)
            except:
                pass

# Start the bot
print("Bot is running...")
app.run()
