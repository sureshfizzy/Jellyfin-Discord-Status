import requests
import discord
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from dateutil import parser, tz

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

# Function to count media items in a library
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

# Function to count media items added in the past 24 hours
def count_recently_added_items(user_id, library_id):
    url = f"{BASE_URL}/Users/{user_id}/Items"
    now = datetime.utcnow().replace(tzinfo=tz.UTC)
    twenty_four_hours_ago = now - timedelta(hours=24)
    params = {
        'Recursive': 'true',
        'ParentId': library_id,
        'IncludeItemTypes': 'Movie,Series',  # Only count movies and series
        'Fields': 'Id,DateCreated',  # Need IDs and DateCreated to filter
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        items = response.json().get('Items', [])
        count = 0
        for item in items:
            date_created = item.get('DateCreated')
            if date_created:
                try:
                    item_date = parser.isoparse(date_created)
                    if item_date.tzinfo is None:
                        item_date = item_date.replace(tzinfo=tz.UTC)
                    if item_date >= twenty_four_hours_ago:
                        count += 1
                except ValueError as e:
                    logger.error(f"Date parsing error for item with DateCreated '{date_created}': {e}")
        return count
    else:
        logger.error(f"Error counting recently added items in library {library_id}: {response.status_code} {response.text}")
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
        recent_counts = {}
        for library in libraries:
            library_name = library['Name']
            if library_name not in ['Playlists', 'Collections']:  # Skip these libraries
                library_id = library['Id']
                count = count_items_in_library(user_id, library_id)
                recent_count = count_recently_added_items(user_id, library_id)
                library_counts[library_name] = count
                if recent_count > 0:
                    recent_counts[library_name] = recent_count
        return library_counts, recent_counts
    else:
        logger.error(f"Error listing libraries: {response.status_code} {response.text}")
        return {}, {}

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

                # Determine the server status
                status = "🟢 **Server Status:** Online" if server_active else "🔴 **Server Status:** Offline"
                color = discord.Color.green() if server_active else discord.Color.red()
                
                # Initialize embed
                embed = discord.Embed(
                    title="Jellyfin Server Status",
                    description=status,
                    color=color
                )
                embed.set_footer(text=f"Last updated at {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                embed.set_thumbnail(url="https://example.com/your-thumbnail.png")  # Optional thumbnail image
                embed.set_author(name="Jellyfin Status Bot", icon_url="https://example.com/your-bot-icon.png")  # Optional author image

                if user_id:
                    library_counts, recent_counts = list_and_count_media_libraries(user_id)

                    # Library count section
                    embed.add_field(name="**📊 Library Counts**", value="Here are the total counts of media items in each library:", inline=False)
                    for lib, count in library_counts.items():
                        embed.add_field(name=f"**{lib}**", value=f"{count} items", inline=True)

                    # Recently added section
                    if recent_counts:
                        recent_description = '\n'.join([f"**{lib}:** {count} items" for lib, count in recent_counts.items()])
                        embed.add_field(name="**🆕 Recently Added (Past 24 Hours)**", value=recent_description, inline=False)
                    else:
                        embed.add_field(name="**🆕 Recently Added (Past 24 Hours)**", value="No items added in the past 24 hours.", inline=False)

                else:
                    embed.add_field(name="**❌ Error**", value='No users found or error retrieving user ID.', inline=False)

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
