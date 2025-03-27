import os
import mmap
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# Bot configuration
API_ID = 21705536  # Replace with your API ID
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token

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

def extract_url_info(line):
    """Extract video name, url and key from a line"""
    if 'http' not in line:
        return None, None, None
    
    # Split on first 'http' to separate name and url
    parts = line.split('http', 1)
    video_name = parts[0].strip()
    url_part = 'http' + parts[1] if len(parts) > 1 else None
    
    if not url_part:
        return video_name, None, None
    
    # Now check for decryption key
    if '*' in url_part:
        url, key = url_part.split('*', 1)
        return video_name, url.strip(), key.strip()
    else:
        return video_name, url_part.strip(), None

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

def get_file_extension(url):
    """Extract file extension from URL"""
    filename = url.split('?')[0].split('#')[0].split('/')[-1]
    if '.' in filename:
        return filename.split('.')[-1].lower()
    return None

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hello! I'm a file decryption bot.\n\n"
        "Upload a .txt file containing your links in this format:\n\n"
        "`Video Name:https://example.com/encrypted.mp4*mysecretkey`\n\n"
        "Or simply:\n"
        "`Video Name:https://example.com/file.mp4`\n\n"
        "Each link should be on a new line. I'll process all valid links."
    )

@app.on_message(filters.document)
async def handle_txt_file(client: Client, message: Message):
    if not message.document.file_name.endswith('.txt'):
        await message.reply_text("❌ Please upload a .txt file containing your links.")
        return
    
    status_msg = await message.reply_text("📥 Downloading your text file...")
    
    try:
        # Download the text file
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        txt_path = os.path.join(temp_dir, "links.txt")
        
        await message.download(file_name=txt_path)
        
        # Read the file
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            await status_msg.edit_text("❌ The text file is empty.")
            return
        
        await status_msg.edit_text(f"🔍 Found {len(lines)} links to process. Starting...")
        
        success_count = 0
        fail_count = 0
        processed_files = []
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            video_name, url, key = extract_url_info(line)
            
            if not url:
                fail_count += 1
                continue
                
            try:
                await status_msg.edit_text(f"⏳ Processing {i}/{len(lines)}: {video_name or 'Unnamed file'}")
                
                # Create temp paths
                encrypted_path = os.path.join(temp_dir, f"temp_{i}.tmp")
                final_path = None
                
                # Download
                if not download_file(url, encrypted_path):
                    fail_count += 1
                    continue
                
                # Decrypt if key exists
                if key:
                    if not decrypt_file(encrypted_path, key):
                        fail_count += 1
                        continue
                
                # Determine final filename
                ext = get_file_extension(url)
                if video_name:
                    safe_name = "".join(c for c in video_name if c.isalnum() or c in (' ', '-', '_'))
                    final_filename = f"{safe_name}.{ext}" if ext else safe_name
                else:
                    final_filename = f"file_{i}.{ext}" if ext else f"file_{i}"
                
                final_path = os.path.join(temp_dir, final_filename)
                os.rename(encrypted_path, final_path)
                processed_files.append(final_path)
                
                # Send to user
                caption = video_name if video_name else f"File {i}"
                await message.reply_document(
                    document=final_path,
                    caption=caption,
                    progress=lambda current, total: print(f"Uploaded {current} of {total} bytes")
                )
                
                success_count += 1
                
            except Exception as e:
                print(f"Error processing line {i}: {e}")
                fail_count += 1
                continue
        
        # Final report
        report = f"✅ Processing complete!\n\nSuccess: {success_count}\nFailed: {fail_count}"
        await status_msg.edit_text(report)
        
    except Exception as e:
        await message.reply_text(f"❌ Error processing file: {str(e)}")
        if 'status_msg' in locals():
            await status_msg.delete()
    
    finally:
        # Clean up
        try:
            if 'txt_path' in locals() and os.path.exists(txt_path):
                os.remove(txt_path)
            
            if 'processed_files' in locals():
                for file_path in processed_files:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except:
                        pass
        except:
            pass

@app.on_message(filters.text & ~filters.command("start"))
async def handle_direct_message(client: Client, message: Message):
    await message.reply_text(
        "📝 Please upload a .txt file containing your links.\n\n"
        "Each line should be in format:\n"
        "`Video Name:https://example.com/file.mp4*key`\n\n"
        "or\n"
        "`Video Name:https://example.com/file.mp4`\n\n"
        "Use /start to see instructions again."
    )

print("Bot is running...")
app.run()
