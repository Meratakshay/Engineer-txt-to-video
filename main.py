import os
import mmap
import time
import logging
import requests
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = 21705536  # Replace with your API ID
API_HASH = "c5bb241f6e3ecf33fe68a444e288de2d"  # Replace with your API HASH
BOT_TOKEN = "7480080731:AAHJ3jgh7npoAJSZ0tiB2n0bqSY0sp5E4gk"  # Replace with your bot token

# Initialize the Pyrogram client
app = Client("file_decryptor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Global variables to store user data
user_data = {}
stop_flags = {}

# Constants
MAX_FILE_SIZE = 2000 * 1024 * 1024  # 2GB Telegram limit
SUPPORTED_VIDEO_EXTENSIONS = ['mp4', 'mkv', 'mov', 'avi', 'webm']
SUPPORTED_DOCUMENT_EXTENSIONS = ['pdf', 'doc', 'docx', 'txt']

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def download_file(url, save_path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        logger.info(f"Downloading file from: {url}")
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        # Check content size
        if 'content-length' in response.headers:
            size = int(response.headers['content-length'])
            if size > MAX_FILE_SIZE:
                raise ValueError("File too large for Telegram upload")

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        logger.info(f"File downloaded successfully at: {save_path}")
        return True
    except Exception as e:
        logger.error(f"Error during download: {e}")
        raise

def extract_url_info(line):
    """Extract video name, url and key from a line with validation"""
    if not line or 'http' not in line:
        return None, None, None
    
    try:
        # Split on first 'http' occurrence
        parts = line.split('http', 1)
        video_name = parts[0].strip(' :')  # Clean name
        url_part = 'http' + parts[1].strip() if len(parts) > 1 else None
        
        if not url_part:
            return None, None, None
        
        # Validate URL structure
        parsed = requests.utils.urlparse(url_part.split('*')[0])
        if not all([parsed.scheme, parsed.netloc]):
            return None, None, None
        
        # Extract key if exists
        if '*' in url_part:
            base_url, key = url_part.split('*', 1)
            return video_name, base_url.strip(), key.strip()
        
        return video_name, url_part.strip(), None
        
    except Exception as e:
        logger.error(f"Error parsing line: {e}")
        return None, None, None

def decrypt_file(file_path, key):
    if not os.path.exists(file_path):
        logger.error("Encrypted file not found!")
        return False
    
    try:
        logger.info(f"Decrypting file: {file_path} with key: {key}")
        with open(file_path, "r+b") as f:
            num_bytes = min(28, os.path.getsize(file_path))
            with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:
                for i in range(num_bytes):
                    mmapped_file[i] ^= ord(key[i % len(key)])
        logger.info("Decryption completed successfully!")
        return True
    except Exception as e:
        logger.error(f"Error during decryption: {e}")
        return False

def get_file_extension(url):
    """Extract file extension from URL"""
    filename = url.split('?')[0].split('#')[0].split('/')[-1]
    if '.' in filename:
        return filename.split('.')[-1].lower()
    return None

def is_video_file(extension):
    return extension in SUPPORTED_VIDEO_EXTENSIONS

def is_document_file(extension):
    return extension in SUPPORTED_DOCUMENT_EXTENSIONS

def create_keyboard_buttons(total_links):
    """Create inline keyboard buttons for link selection"""
    buttons = []
    row = []
    for i in range(1, total_links + 1):
        row.append(InlineKeyboardButton(str(i), callback_data=f"process_{i}"))
        if len(row) == 5:  # 5 buttons per row
            buttons.append(row)
            row = []
    if row:  # Add remaining buttons
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Process All", callback_data="process_all")])
    buttons.append([InlineKeyboardButton("Cancel", callback_data="cancel_process")])
    return buttons

def create_failure_message(item):
    """Create a formatted failure message for a single item"""
    message = "❌ Download Failed\n\n"
    message += f"🔢 File Number: #{item['number']}\n"
    message += f"📛 Name: {item['name'] or 'Unnamed'}\n"
    message += f"🔗 URL: {item['url']}\n"
    message += f"❗ Error: {item['error']}\n"
    return message

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "👋 Hello! I'm an advanced file decryption bot.\n\n"
        "📁 Upload a .txt file containing your links in this format:\n\n"
        "`Video Name:https://example.com/encrypted.mp4*mysecretkey`\n\n"
        "Or simply:\n"
        "`Video Name:https://example.com/file.mp4`\n\n"
        "Each link should be on a new line. I'll process all valid links.\n\n"
        "After upload, I'll ask which links you want to process.\n\n"
        "Commands:\n"
        "/start - Show this message\n"
        "/stop - Stop current processing\n"
        "/failed - Show failed downloads"
    )

@app.on_message(filters.command("stop"))
async def stop_command(client: Client, message: Message):
    user_id = message.from_user.id
    stop_flags[user_id] = True
    await message.reply_text("🛑 Stopping current processing...")
    logger.info(f"User {user_id} requested to stop processing")

@app.on_message(filters.document)
async def handle_txt_file(client: Client, message: Message):
    if not message.document.file_name.endswith('.txt'):
        await message.reply_text("❌ Please upload a .txt file containing your links.")
        return
    
    user_id = message.from_user.id
    stop_flags[user_id] = False  # Reset stop flag
    
    status_msg = await message.reply_text("📥 Downloading your text file...")
    
    try:
        # Download the text file
        temp_dir = "temp_files"
        os.makedirs(temp_dir, exist_ok=True)
        txt_path = os.path.join(temp_dir, f"links_{user_id}.txt")
        
        await message.download(file_name=txt_path)
        
        # Read the file
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        
        if not lines:
            await status_msg.edit_text("❌ The text file is empty.")
            return
        
        # Store user data
        user_data[user_id] = {
            'txt_path': txt_path,
            'lines': lines,
            'current_index': 0,
            'processed_files': [],
            'failed_downloads': []
        }
        
        # Create selection keyboard
        keyboard = InlineKeyboardMarkup(create_keyboard_buttons(len(lines)))
        
        await status_msg.edit_text(
            f"🔍 Found {len(lines)} links. Which one do you want to process?",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error processing text file: {e}")
        await message.reply_text(f"❌ Error processing file: {str(e)}")
        if 'status_msg' in locals():
            await status_msg.delete()

@app.on_callback_query(filters.regex(r"^process_(\d+|all|cancel)$"))
async def process_selected_link(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in user_data:
        await callback_query.answer("Session expired. Please upload the file again.", show_alert=True)
        return
    
    if data == "cancel_process":
        stop_flags[user_id] = True
        await callback_query.answer("Processing will stop after current file", show_alert=True)
        await callback_query.message.edit_text("🛑 Cancelling processing...")
        return
    
    try:
        await callback_query.answer()
        
        lines = user_data[user_id]['lines']
        processing_msg = await callback_query.message.reply_text("⏳ Starting processing...")
        failed_items = []
        
        if data == "process_all":
            # Process all links
            start_idx = 0
            end_idx = len(lines)
        else:
            # Process single link
            link_num = int(data.split('_')[1]) - 1  # Convert to 0-based index
            start_idx = link_num
            end_idx = link_num + 1
        
        success_count = 0
        
        for i in range(start_idx, end_idx):
            if stop_flags.get(user_id, False):
                await processing_msg.edit_text("🛑 Processing stopped by user")
                stop_flags[user_id] = False  # Reset flag
                break
            
            line = lines[i]
            video_name, url, key = extract_url_info(line)
            
            if not url:
                failed_item = {
                    'number': i+1,
                    'name': video_name,
                    'url': 'Invalid URL format',
                    'error': 'Could not extract valid URL'
                }
                failed_items.append(failed_item)
                await callback_query.message.reply_text(create_failure_message(failed_item))
                continue
                
            try:
                await processing_msg.edit_text(f"⏳ Processing #{i+1}: {video_name or 'Unnamed file'}")
                
                # Create temp paths
                temp_dir = "temp_files"
                encrypted_path = os.path.join(temp_dir, f"temp_{user_id}_{i}.tmp")
                final_path = None
                
                # Download
                try:
                    if not download_file(url, encrypted_path):
                        raise Exception("Download failed after retries")
                except Exception as e:
                    failed_item = {
                        'number': i+1,
                        'name': video_name,
                        'url': url,
                        'error': str(e)
                    }
                    failed_items.append(failed_item)
                    await callback_query.message.reply_text(create_failure_message(failed_item))
                    continue
                
                # Decrypt if key exists
                if key:
                    if not decrypt_file(encrypted_path, key):
                        failed_item = {
                            'number': i+1,
                            'name': video_name,
                            'url': url,
                            'error': "Decryption failed - invalid key"
                        }
                        failed_items.append(failed_item)
                        await callback_query.message.reply_text(create_failure_message(failed_item))
                        continue
                
                # Determine file type and extension
                ext = get_file_extension(url)
                if video_name:
                    safe_name = "".join(c for c in video_name if c.isalnum() or c in (' ', '-', '_'))
                    final_filename = f"{safe_name}.{ext}" if ext else safe_name
                else:
                    final_filename = f"file_{i+1}.{ext}" if ext else f"file_{i+1}"
                
                final_path = os.path.join(temp_dir, final_filename)
                os.rename(encrypted_path, final_path)
                user_data[user_id]['processed_files'].append(final_path)
                
                # Send to user based on file type
                caption = f"#{i+1} - {video_name}" if video_name else f"File #{i+1}"
                
                try:
                    if ext and is_video_file(ext):
                        # Send as playable video
                        await callback_query.message.reply_video(
                            video=final_path,
                            caption=caption,
                            supports_streaming=True,
                            progress=lambda current, total: logger.info(f"Uploaded {current} of {total} bytes")
                        )
                    elif ext and is_document_file(ext):
                        # Send as document
                        await callback_query.message.reply_document(
                            document=final_path,
                            caption=caption,
                            progress=lambda current, total: logger.info(f"Uploaded {current} of {total} bytes")
                        )
                    else:
                        # Generic file send
                        await callback_query.message.reply_document(
                            document=final_path,
                            caption=caption,
                            progress=lambda current, total: logger.info(f"Uploaded {current} of {total} bytes")
                        )
                    
                    success_count += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    continue
                except Exception as e:
                    failed_item = {
                        'number': i+1,
                        'name': video_name,
                        'url': url,
                        'error': f"Failed to send file: {str(e)}"
                    }
                    failed_items.append(failed_item)
                    await callback_query.message.reply_text(create_failure_message(failed_item))
                    continue
                
            except Exception as e:
                logger.error(f"Error processing line {i+1}: {e}")
                failed_item = {
                    'number': i+1,
                    'name': video_name,
                    'url': url,
                    'error': str(e)
                }
                failed_items.append(failed_item)
                await callback_query.message.reply_text(create_failure_message(failed_item))
                continue
        
        # Final report
        report = f"✅ Processing complete!\n\nSuccess: {success_count}\nFailed: {len(failed_items)}"
        
        # Store failed items
        if failed_items:
            user_data[user_id]['failed_downloads'] = failed_items
            report += "\n\nSend /failed to see details of all failed downloads"
        
        await processing_msg.edit_text(report)
        
    except Exception as e:
        logger.error(f"Error in callback processing: {e}")
        await callback_query.message.reply_text(f"❌ Error during processing: {str(e)}")
    
    finally:
        # Clean up processed files
        if user_id in user_data and 'processed_files' in user_data[user_id]:
            for file_path in user_data[user_id]['processed_files']:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
        stop_flags[user_id] = False  # Reset stop flag

@app.on_message(filters.command("failed"))
async def show_failed_downloads(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_data or not user_data[user_id].get('failed_downloads'):
        await message.reply_text("No failed downloads to show.")
        return
    
    failed_items = user_data[user_id]['failed_downloads']
    
    # Send each failure as a separate message
    for item in failed_items:
        await message.reply_text(create_failure_message(item))
    
    await message.reply_text(f"Total failed downloads: {len(failed_items)}")

@app.on_message(filters.text & ~filters.command(["start", "stop", "failed"]))
async def handle_direct_message(client: Client, message: Message):
    await message.reply_text(
        "📝 Please upload a .txt file containing your links.\n\n"
        "Each line should be in format:\n"
        "`Video Name:https://example.com/file.mp4*key`\n\n"
        "or\n"
        "`Video Name:https://example.com/file.mp4`\n\n"
        "After upload, I'll ask which links you want to process.\n\n"
        "Commands:\n"
        "/start - Show instructions\n"
        "/stop - Stop current processing\n"
        "/failed - Show failed downloads"
    )

if __name__ == "__main__":
    # Create temp directory if not exists
    os.makedirs("temp_files", exist_ok=True)
    logger.info("Bot is running...")
    app.run()
