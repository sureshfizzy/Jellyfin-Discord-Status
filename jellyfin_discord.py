import requests
import discord
import asyncio
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set your API key and base URL for Jellyfin
API_KEY = 'your_jellyfin_api_key'
BASE_URL = 'your_jellyfin_base_url'
headers = {
    'X-Emby-Token': API_KEY,
    'Accept': 'application/json'
}

# Set Discord bot token and guild ID
DISCORD_TOKEN = 'your_discord_bot_token'
DISCORD_GUILD_ID = your_discord_channel-ID  # Your server (guild) ID
CHANNEL_NAME = 'jellyfin-status-bot'
CATEGORY_NAME = 'Jellyfin Status'
MESSAGE_FILE = 'last_message_id.json'

# Function to get all users and extract the first user's ID
def get_first_user_id():
    url = f"{BASE_URL}/Users"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        users = response.json()
        if users:
            return users[0]['Id']  # Returning the first user's ID
        else:
            logger.warning("No users found.")
            return None
    else:
        logger.error(f"Error getting users: {response.status_code} {response.text}")
        return None

# Function to count media items (excluding episodes)
def count_items_in_library(user_id, library_id):
    url = f"{BASE_URL}/Users/{user_id}/Items"
    params = {
        'Recursive': 'true',
        'ParentId': library_id,
        'IncludeItemTypes': 'Movie,Series',  # Only count movies and series
        'Fields': 'Id',  # Only need IDs to count
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        items = response.json().get('TotalRecordCount', 0)
        return items
    else:
        logger.error(f"Error counting items in library {library_id}: {response.status_code} {response.text}")
        return 0

# Function to list media libraries and count items in each
def list_and_count_media_libraries(user_id):
    url = f"{BASE_URL}/Users/{user_id}/Items"
    params = {
        'Recursive': 'false',
        'IncludeItemTypes': 'Folder',  # Filter for libraries
        'ParentId': '',  # Root level libraries
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        libraries = response.json().get('Items', [])
        library_counts = {}
        for library in libraries:
            library_name = library['Name']
            if library_name not in ['Playlists', 'Collections']:  # Skip these libraries
                library_id = library['Id']
                count = count_items_in_library(user_id, library_id)
                library_counts[library_name] = count
        return library_counts
    else:
        logger.error(f"Error listing libraries: {response.status_code} {response.text}")
        return {}

# Function to check if the server is active
def check_server_status():
    try:
        response = requests.get(BASE_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Exception occurred while checking server status: {e}")
        return False

# Function to save the message ID to a file
def save_message_id(message_id):
    with open(MESSAGE_FILE, 'w') as f:
        json.dump({'message_id': message_id}, f)
    logger.info(f"Saved message ID: {message_id}")

# Function to load the message ID from a file
def load_message_id():
    if os.path.exists(MESSAGE_FILE):
        with open(MESSAGE_FILE, 'r') as f:
            data = json.load(f)
            message_id = data.get('message_id')
            logger.info(f"Loaded message ID: {message_id}")
            return message_id
    return None

# Function to create or fetch a category and channel
async def get_or_create_category_and_channel(guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)
        logger.info(f"Created category: {CATEGORY_NAME}")
    
    channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME, category=category)
    if not channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True),
        }
        channel = await guild.create_text_channel(CHANNEL_NAME, category=category, overwrites=overwrites)
        logger.info(f"Created channel: {CHANNEL_NAME} in category: {CATEGORY_NAME}")
    
    return channel

# Function to update the rich embed message on Discord
async def update_discord_message():
    global previous_message_id
    guild = discord.utils.get(client.guilds, id=DISCORD_GUILD_ID)
    if guild:
        channel = await get_or_create_category_and_channel(guild)
        while True:
            try:
                server_active = check_server_status()
                user_id = get_first_user_id()

                if server_active:
                    status = "🟢 **Server Status:** Online"
                else:
                    status = "🔴 **Server Status:** Offline"

                if user_id:
                    library_counts = list_and_count_media_libraries(user_id)
                    description = '\n'.join([f"**{lib}:** {count}" for lib, count in library_counts.items()])
                else:
                    description = 'No users found or error retrieving user ID.'

                embed = discord.Embed(
                    title="Jellyfin Server Status & Media Library Counts",
                    description=status + '\n\n' + description,
                    color=discord.Color.green() if server_active else discord.Color.red()
                )

                if previous_message_id:
                    try:
                        message = await channel.fetch_message(previous_message_id)
                        await message.edit(embed=embed)
                        logger.info(f"Successfully edited message with ID: {previous_message_id}")
                    except discord.NotFound:
                        logger.warning("Previous message not found, creating a new one.")
                        previous_message_id = None  # Reset ID if message not found
                if not previous_message_id:
                    message = await channel.send(embed=embed)
                    previous_message_id = message.id
                    save_message_id(previous_message_id)
                    logger.info(f"Created new message with ID: {previous_message_id}")

                await asyncio.sleep(60)  # Wait for 60 seconds before updating again
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                await asyncio.sleep(60)  # Wait before retrying in case of an error

# Main bot functionality
intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    global previous_message_id
    logger.info(f'Logged in as {client.user}')
    previous_message_id = load_message_id()
    asyncio.create_task(update_discord_message())  # Start the update loop

client.run(DISCORD_TOKEN)
