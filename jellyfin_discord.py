import requests
import discord
import re
import pytz
import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from dateutil import parser, tz
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure the log directory exists
LOG_FILE = os.getenv('LOG_FILE')  # Provide a default value if not set
log_directory = os.path.dirname(LOG_FILE)
if log_directory and not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set the log level

# Create file handler and set level to info (overwrite log file)
file_handler = logging.FileHandler(LOG_FILE, mode='w')  # 'w' mode clears the file
file_handler.setLevel(logging.INFO)

# Create stream handler (console output) and set level to info
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Test logging setup
logger.info("Logging initialized successfully.")

# Set your API key and base URL for Jellyfin
API_KEY = os.getenv('JELLYFIN_API_KEY')
BASE_URL = os.getenv('JELLYFIN_BASE_URL')
headers = {
    'X-Emby-Token': API_KEY,
    'Accept': 'application/json'
}

# Set Discord bot token and guild ID
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
CHANNEL_NAME = os.getenv('CHANNEL_NAME')
CATEGORY_NAME = os.getenv('CATEGORY_NAME')
MESSAGE_FILE = os.getenv('MESSAGE_FILE')
TIMEZONE = os.getenv('TIMEZONE')
SLEEP_DURATION = int(os.getenv('SLEEP_DURATION'))
THUMBNAIL_URL = os.getenv('THUMBNAIL_URL')
AUTHOR_ICON_URL = os.getenv('AUTHOR_ICON_URL')
CHANNEL_TYPE = os.getenv('CHANNEL_TYPE').lower()
USER_ID = os.getenv('USER_ID')

# Ensure USER_ID is set
if not USER_ID:
    logger.error("USER_ID is not set in the .env file.")
    raise ValueError("USER_ID is required but not set in the .env file.")

# Function to count media items in a library
def count_items_in_library(user_id, library_id):
    url = f"{BASE_URL}/Users/{user_id}/Items"
    params = {
        'Recursive': 'true',
        'ParentId': library_id,
        'IncludeItemTypes': 'Movie,Series,Episode,MusicVideo',
        'Fields': 'Id,Type',
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        items = response.json().get('Items', [])
        movie_count = sum(1 for item in items if item['Type'] == 'Movie')
        series_count = sum(1 for item in items if item['Type'] == 'Series')
        episode_count = sum(1 for item in items if item['Type'] == 'Episode')
        music_video_count = sum(1 for item in items if item['Type'] == 'MusicVideo')  # Count music videos
        return movie_count, series_count, episode_count, music_video_count
    else:
        logger.error(f"Error counting items in library {library_id}: {response.status_code} {response.text}")
        return 0, 0, 0, 0

# Function to count media items added in the past 24 hours
def count_recently_added_items(user_id, library_id):
    url = f"{BASE_URL}/Users/{user_id}/Items"
    now = datetime.utcnow().replace(tzinfo=tz.UTC)
    twenty_four_hours_ago = now - timedelta(hours=24)
    params = {
        'Recursive': 'true',
        'ParentId': library_id,
        'IncludeItemTypes': 'Movie,Series,MusicVideo',  # Include music videos
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

            if library_name not in ['Playlists', 'Collections', 'Recommendations', 'Recordings']:
                library_id = library['Id']
                movie_count, series_count, episode_count, music_video_count = count_items_in_library(user_id, library_id)
                recent_count = count_recently_added_items(user_id, library_id)

                if library.get('CollectionType') == 'movies' or 'Movies' in library_name:
                    # Movies library: only count movies
                    library_counts[library_name] = f"{movie_count} Movies"
                elif library.get('CollectionType') == 'tvshows' or 'Shows' in library_name:
                    # Shows library: count shows and episodes
                    if episode_count > 0:
                        library_counts[library_name] = f"{series_count} Shows / {episode_count} Episodes"
                    else:
                        library_counts[library_name] = f"{series_count} Shows"
                elif library.get('CollectionType') == 'musicvideos' or 'Music Videos' in library_name:
                    # Music Videos library: count music videos
                    library_counts[library_name] = f"{music_video_count} Music Videos"
                else:
                    # Default fallback: unknown type
                    library_counts[library_name] = f"{movie_count} Movies / {series_count} Shows / {music_video_count} Music Videos"

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

async def get_or_create_category_and_channel(guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        category = await guild.create_category(CATEGORY_NAME)
        logger.info(f"Created category: {CATEGORY_NAME}")
    
    # Define channel overwrites for permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),  # Prevent sending messages
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # Allow bot to send messages
    }

    # Try to find an existing channel in the category
    existing_channel = None
    for channel in guild.text_channels:
        if channel.category == category and channel.name.lower() == CHANNEL_NAME.lower():
            existing_channel = channel
            break
    
    if existing_channel:
        if CHANNEL_TYPE == 'announcement' and existing_channel.type != discord.ChannelType.news:
            # Update text channel to announcement
            await existing_channel.edit(type=discord.ChannelType.news)
            logger.info(f"Updated channel {CHANNEL_NAME} to announcement type")
        elif CHANNEL_TYPE == 'text' and existing_channel.type == discord.ChannelType.news:
            # Update announcement channel to text
            await existing_channel.edit(type=discord.ChannelType.text)
            logger.info(f"Updated channel {CHANNEL_NAME} to text type")
        # If the existing channel type matches the required type, do nothing
    else:
        if CHANNEL_TYPE == 'text':
            # Create a text channel
            channel = await guild.create_text_channel(
                CHANNEL_NAME,
                category=category,
                overwrites=overwrites
            )
        elif CHANNEL_TYPE == 'voice':
            # Create a voice channel
            channel = await guild.create_voice_channel(
                CHANNEL_NAME,
                category=category,
                overwrites=overwrites
            )
        elif CHANNEL_TYPE == 'announcement':
            # Create an announcement channel
            channel = await guild.create_text_channel(
                CHANNEL_NAME,
                category=category,
                overwrites=overwrites
            )
            await channel.edit(type=discord.ChannelType.news)
        else:
            logger.error(f"Unknown channel type: {CHANNEL_TYPE}")
            return None
        
        logger.info(f"Created {CHANNEL_TYPE} channel: {CHANNEL_NAME} in category: {CATEGORY_NAME}")
    
    return existing_channel or channel

# Function to update the rich embed message on Discord
async def update_discord_message():
    global previous_message_id
    guild = discord.utils.get(client.guilds, id=DISCORD_GUILD_ID)
    if guild:
        channel = await get_or_create_category_and_channel(guild)
        while True:
            try:
                # Use USER_ID directly
                user_id = USER_ID

                # Initialize embed
                embed = discord.Embed(
                    title="JellyCine Media Library Overview",
                    description="Here's the latest status of your JellyCine media libraries.",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Last updated at {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
                embed.set_thumbnail(url=THUMBNAIL_URL)  # Thumbnail image from .env
                embed.set_author(name="Jellyfin Status Bot", icon_url=AUTHOR_ICON_URL)  # Author image from .env

                if user_id:
                    library_counts, recent_counts = list_and_count_media_libraries(user_id)

                    # Library count section
                    embed.add_field(name="📚 Library Totals", value="Here's the count of media items in each library:", inline=False)
                    for lib, count in library_counts.items():
                        embed.add_field(name=f"**{lib}**", value=count, inline=True)

                    # Recently added section
                    if recent_counts:
                        recent_description = '\n'.join([f"**{lib}:** {count} new items" for lib, count in recent_counts.items()])
                        embed.add_field(name="🆕 Recently Added (Last 24 Hours)", value=recent_description, inline=False)
                    else:
                        embed.add_field(name="🆕 Recently Added (Last 24 Hours)", value="No new items have been added in the past 24 hours.", inline=False)

                else:
                    embed.add_field(name="❌ Error", value='Unable to retrieve user information. Please check the Jellyfin server configuration.', inline=False)

                if previous_message_id:
                    try:
                        message = await channel.fetch_message(previous_message_id)
                        await message.edit(embed=embed)
                        logger.info(f"Successfully updated message with ID: {previous_message_id}")
                    except discord.NotFound:
                        logger.warning("Previous message not found, creating a new one.")
                        previous_message_id = None  # Reset ID if message not found
                if not previous_message_id:
                    message = await channel.send(embed=embed)
                    previous_message_id = message.id
                    save_message_id(previous_message_id)
                    logger.info(f"Created new message with ID: {previous_message_id}")

                # Calculate time until the next update
                now = datetime.now(pytz.timezone(TIMEZONE))  # Current time in specified timezone
                next_update_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(seconds=SLEEP_DURATION)
                remaining_time = next_update_time - now
                logger.info(f"Current {TIMEZONE} time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"Next update scheduled in {remaining_time}")
                logger.info(f"Current {TIMEZONE} time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"Next update scheduled at {next_update_time.strftime('%Y-%m-%d %H:%M:%S')}. Remaining time: {remaining_time}")

                await asyncio.sleep(remaining_time.total_seconds())
                #await asyncio.sleep(UPDATE_INTERVAL)  # Wait for the configured interval before updating again
            except Exception as e:
                logger.error(f"An error occurred: {e}")
                await asyncio.sleep(SLEEP_DURATION)  # Wait before retrying in case of an error

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
