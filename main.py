#Telegram Speed Downloader Bot
#Developer: Alien

import asyncio
import time
import os
import json
import shutil
from datetime import datetime
from hydrogram import Client, filters
from hydrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from hydrogram.enums import ParseMode

CONFIG_FILE = "config.json"

def load_config():
    """Load configuration from JSON or prompt user to create it."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    
    print("Settings file not found. Please enter your credentials:")
    config = {
        "API_ID": int(input("Enter API_ID: ")),
        "API_HASH": input("Enter API_HASH: "),
        "BOT_TOKEN": input("Enter BOT_TOKEN: "),
        "DOWNLOAD_DIR": input("Enter DOWNLOAD_DIR (default './downloads/'): ") or "./downloads/"
    }
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print(f"Configuration saved to {CONFIG_FILE}\n")
    return config

# Load settings
config = load_config()
API_ID = config["API_ID"]
API_HASH = config["API_HASH"]
BOT_TOKEN = config["BOT_TOKEN"]
DOWNLOAD_DIR = config["DOWNLOAD_DIR"]

# Ensure DOWNLOAD_DIR is properly formatted
DOWNLOAD_DIR = DOWNLOAD_DIR.rstrip('/') + '/'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

app = Client(
    "speed_downloader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    max_concurrent_transmissions=12, 
    workers=20,
    parse_mode=ParseMode.MARKDOWN
)

# Create persistent keyboard menu
def get_main_keyboard():
    """Return the main keyboard with management buttons"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton("📁 View Files"),
                KeyboardButton("🗑️ Delete Files")
            ],
            [
                KeyboardButton("📦 Move Files"),
                KeyboardButton("❌ Delete All")
            ],
            [
                KeyboardButton("ℹ️ Status")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def get_delete_keyboard():
    """Return keyboard for delete options"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton("🗑️ Delete Files Only"),
                KeyboardButton("🗑️ Delete All (Including Folders)")
            ],
            [
                KeyboardButton("🔙 Back to Main Menu")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def human_size(size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"  # Handle very large sizes

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Send welcome message with keyboard menu"""
    welcome_text = (
        "**🤖 Welcome to Speed Downloader Bot!**\n\n"
        "Send me any file, video, or audio, and I'll download it with high speed.\n\n"
        "**Available Actions:**\n"
        "• 📁 View Files - List all downloaded files\n"
        "• 🗑️ Delete Files - Remove files from storage\n"
        "• 📦 Move Files - Organize files into dated folders\n"
        "• ℹ️ Status - Check bot status and storage info\n\n"
        "Use the buttons below to manage your files!"
    )
    await message.reply(welcome_text, reply_markup=get_main_keyboard())

@app.on_message(filters.text & ~filters.command(["start"]))
async def handle_menu_buttons(client, message: Message):
    """Handle text menu button presses"""
    text = message.text
    
    if text == "📁 View Files":
        await view_files(client, message)
    elif text == "🗑️ Delete Files":
        await message.reply(
            "**🗑️ Delete Options**\n\n"
            "Choose what you want to delete:",
            reply_markup=get_delete_keyboard()
        )
    elif text == "🗑️ Delete Files Only":
        await delete_files_only(client, message)
    elif text == "🗑️ Delete All (Including Folders)":
        await delete_all_items(client, message)
    elif text == "📦 Move Files":
        await move_files(client, message)
    elif text == "ℹ️ Status":
        await show_status(client, message)
    elif text == "❌ Delete All":
        await confirm_delete_all(client, message)
    elif text == "🔙 Back to Main Menu":
        await message.reply(
            "**🔙 Returning to Main Menu**",
            reply_markup=get_main_keyboard()
        )

async def confirm_delete_all(client, message: Message):
    """Confirm before deleting all files"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("✅ Confirm Delete All")],
            [KeyboardButton("🔙 Back to Main Menu")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    await message.reply(
        "⚠️ **WARNING: This will delete ALL files and folders!**\n\n"
        "Are you sure you want to proceed?",
        reply_markup=keyboard
    )
    
    # Wait for response
    @app.on_message(filters.text & filters.user(message.from_user.id) & ~filters.command(["start"]), group=1)
    async def handle_confirm(client, confirm_msg):
        if confirm_msg.text == "✅ Confirm Delete All":
            await delete_all_items(client, confirm_msg)
        elif confirm_msg.text == "🔙 Back to Main Menu":
            await confirm_msg.reply(
                "**Operation cancelled.**",
                reply_markup=get_main_keyboard()
            )
        # Remove this handler after use
        app.remove_handler(handle_confirm)

async def view_files(client, message: Message):
    """Show list of downloaded files"""
    try:
        items = os.listdir(DOWNLOAD_DIR)
        if not items:
            await message.reply("📂 **No files found in storage.**")
            return
        
        # Separate files and folders
        file_list = []
        folder_list = []
        
        for item in items:
            # Skip the bot's own files and hidden files
            if item.startswith('.') or item == 'speed_downloader':
                continue
                
            item_path = os.path.join(DOWNLOAD_DIR, item)
            try:
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    file_list.append(f"📄 `{item}` ({human_size(size)})")
                elif os.path.isdir(item_path):
                    # Count files in folder
                    folder_files = sum(1 for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f)))
                    folder_list.append(f"📁 `{item}` ({folder_files} files)")
            except (OSError, PermissionError):
                continue
        
        response = "**📁 Downloaded Files:**\n\n"
        if file_list:
            response += "**Files:**\n" + "\n".join(file_list[:20])
            if len(file_list) > 20:
                response += f"\n... and {len(file_list) - 20} more files"
        
        if folder_list:
            response += "\n\n**Folders:**\n" + "\n".join(folder_list[:10])
            if len(folder_list) > 10:
                response += f"\n... and {len(folder_list) - 10} more folders"
        
        # Split message if too long
        if len(response) > 4096:
            parts = [response[i:i+4096] for i in range(0, len(response), 4096)]
            for part in parts:
                await message.reply(part)
        else:
            await message.reply(response)
            
    except Exception as e:
        await message.reply(f"❌ **Error:** `{str(e)}`")

async def delete_files_only(client, message: Message):
    """Delete only files, preserve folders"""
    try:
        items = os.listdir(DOWNLOAD_DIR)
        if not items:
            await message.reply("📂 **No files found to delete.**")
            return
        
        deleted_count = 0
        for item in items:
            item_path = os.path.join(DOWNLOAD_DIR, item)
            if os.path.isfile(item_path):
                try:
                    os.remove(item_path)
                    deleted_count += 1
                except (OSError, PermissionError):
                    continue
        
        await message.reply(
            f"🗑️ **Deleted {deleted_count} file(s) from:** `{DOWNLOAD_DIR}`\n📁 **Folders were preserved.**",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ **Error deleting files:** `{str(e)}`")

async def delete_all_items(client, message: Message):
    """Delete everything (files and folders)"""
    try:
        items = os.listdir(DOWNLOAD_DIR)
        if not items:
            await message.reply("📂 **No files/folders found to delete.**")
            return
        
        deleted_count = 0
        for item in items:
            # Skip the bot's own session file
            if item == 'speed_downloader.session' or item == 'speed_downloader.session-journal':
                continue
                
            item_path = os.path.join(DOWNLOAD_DIR, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    deleted_count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_count += 1
            except (OSError, PermissionError) as e:
                print(f"Error deleting {item_path}: {e}")
                continue
        
        await message.reply(
            f"🗑️ **Deleted {deleted_count} item(s) (files and folders) from:** `{DOWNLOAD_DIR}`",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ **Error deleting items:** `{str(e)}`")

async def move_files(client, message: Message):
    """Move all files to a new folder with current date and time"""
    try:
        items = os.listdir(DOWNLOAD_DIR)
        if not items:
            await message.reply("📂 **No files found to move.**")
            return
        
        # Create folder name with current date and time
        folder_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_folder_path = os.path.join(DOWNLOAD_DIR, folder_name)
        
        os.makedirs(new_folder_path, exist_ok=True)
        
        moved_count = 0
        for item in items:
            # Skip the bot's own session file and new folder
            if item in ['speed_downloader.session', 'speed_downloader.session-journal', folder_name]:
                continue
                
            source_path = os.path.join(DOWNLOAD_DIR, item)
            destination_path = os.path.join(new_folder_path, item)
            try:
                shutil.move(source_path, destination_path)
                moved_count += 1
            except (OSError, PermissionError):
                continue
        
        await message.reply(
            f"📁 **Moved {moved_count} item(s) to:**\n"
            f"`{new_folder_path}`",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await message.reply(f"❌ **Error moving files:** `{str(e)}`")

async def show_status(client, message: Message):
    """Show bot status and storage information"""
    try:
        # Calculate total storage used
        total_size = 0
        file_count = 0
        folder_count = 0
        
        for item in os.listdir(DOWNLOAD_DIR):
            if item in ['speed_downloader.session', 'speed_downloader.session-journal']:
                continue
                
            item_path = os.path.join(DOWNLOAD_DIR, item)
            try:
                if os.path.isfile(item_path):
                    total_size += os.path.getsize(item_path)
                    file_count += 1
                elif os.path.isdir(item_path):
                    folder_count += 1
                    # Count files in folder recursively
                    for root, dirs, files in os.walk(item_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                                file_count += 1
                            except (OSError, PermissionError):
                                continue
            except (OSError, PermissionError):
                continue
        
        # Get disk usage info
        try:
            disk_usage = shutil.disk_usage(DOWNLOAD_DIR)
            free_space = human_size(disk_usage.free)
            total_space = human_size(disk_usage.total)
        except:
            free_space = "Unknown"
            total_space = "Unknown"
        
        status_text = (
            f"**ℹ️ Bot Status**\n\n"
            f"**Storage Location:** `{DOWNLOAD_DIR}`\n"
            f"**Total Files:** {file_count}\n"
            f"**Folders:** {folder_count}\n"
            f"**Total Size:** {human_size(total_size)}\n"
            f"**Free Space:** {free_space}\n"
            f"**Total Space:** {total_space}\n"
            f"**Max Concurrent Downloads:** 12\n"
            f"**Workers:** 20\n\n"
            f"**Bot is running smoothly! 🚀**"
        )
        
        await message.reply(status_text, reply_markup=get_main_keyboard())
    except Exception as e:
        await message.reply(f"❌ **Error:** `{str(e)}`")

@app.on_message(filters.document | filters.video | filters.audio)
async def fast_download_handler(client, message: Message):
    """Handle file downloads"""
    # Determine file name
    media = message.document or message.video or message.audio
    file_name = getattr(media, 'file_name', f"file_{int(time.time())}")
    
    status_msg = await message.reply(f"⚡ **Downloading:** `{file_name}`", quote=True)
    start_time = time.time()

    try:
        # Download the file
        file_path = await client.download_media(
            message,
            file_name=DOWNLOAD_DIR
        )
        
        total_time = round(time.time() - start_time)
        minutes = total_time // 60
        seconds = total_time % 60
        
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        await status_msg.edit(
            f"✅ **Download Finished!**\n\n"
            f"**File:** `{os.path.basename(file_path)}`\n"
            f"**Saved to:** `{file_path}`\n"
            f"**Total Time:** {time_str}"
        )
    except Exception as e:
        await status_msg.edit(f"❌ **Error occurred:** `{str(e)}`")

if __name__ == "__main__":
    print("Bot is starting with high-speed profile on Python 3.14...")
    try:
        loop.run_until_complete(app.run())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
