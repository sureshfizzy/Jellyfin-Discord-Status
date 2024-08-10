# JellyCine Discord Bot

## Overview

The JellyCine Discord Bot integrates with Jellyfin to provide Updates about your media libraries on Discord. It fetches media counts, recently added items, and updates a rich embed message in a designated Discord channel.

![Final Output](https://i.imgur.com/F5SS5Ug.png)

## Prerequisites

- **Python 3.8+**
- **Discord Bot Token**
- **Jellyfin API Key**

## Key Features

- **Fast Processing:** Counts will be displayed quick. 
- **Regular Interval  Updates:** Automatically updates a Discord channel with the latest media statistics from Jellyfin.
- **Media Library Counts:** Provides a detailed count of movies, shows, and episodes in each Jellyfin library.
- **Recently Added Items:** Displays the number of items added to libraries in the past 24 hours.
- **Dynamic Embeds:** Uses rich embeds to format messages with a thumbnail and author icon.
- **Configurable Intervals:** Adjust the update frequency with a customizable sleep duration.
- **Logging:** Tracks bot activity and errors with detailed logging.

## Installation

1. **Clone the Repository:**

    ```sh
    git clone https://github.com/yourusername/jellycine-discord-bot.git
    cd jellycine-discord-bot
    ```

2. **Install Dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

3. **Edit the `.env` File:**

    Update your `.env` file with the required configuration values.

## Configuration

| Environment Variable | Description                                           |
|----------------------|-------------------------------------------------------|
| `JELLYFIN_API_KEY`   | Your Jellyfin API key.                               |
| `JELLYFIN_BASE_URL`  | Base URL of your Jellyfin server.                    |
| `DISCORD_TOKEN`      | Token for your Discord bot.                          |
| `DISCORD_GUILD_ID`   | ID of your Discord guild (server).                    |
| `CHANNEL_NAME`       | Name of the Discord channel to update.               |
| `CATEGORY_NAME`      | Name of the category where the channel resides.      |
| `MESSAGE_FILE`       | Path to the file where the message ID is saved.      |
| `TIMEZONE`           | Your timezone (e.g., `Asia/Kolkata`).                |
| `SLEEP_DURATION`     | Duration between updates in seconds.                |
| `THUMBNAIL_URL`      | URL for the thumbnail image in the embed.           |
| `AUTHOR_ICON_URL`    | URL for the author icon image in the embed.         |
| `CHANNEL_TYPE`       | Type of channel (`text`, `voice`, `announcement`).  |
| `LOG_FILE`           | Path to the log file.                               |

## Enabling Developer Mode in Discord

To enable Developer Mode in Discord:
1. Go to User Settings > Advanced.
2. Toggle on Developer Mode.

![Developer Mode](https://i.imgur.com/JdWaRKp.png)

## Setting the Server to Community Mode

For the `CHANNEL_TYPE=announcement` option to work:
1. Ensure your server is set to Community server mode.
2. This setting can be found in Server Settings under the Community section.

## Usage

1. **Run the Bot:**

    ```sh
    python jellyfin_discord.py
    ```

2. **Monitoring Updates:**

    The bot will automatically update the designated Discord channel with the latest media library status based on the configured interval.

## Troubleshooting

- **Invalid API Key or URL:** Verify your Jellyfin API key and base URL.
- **Permission Issues:** Ensure the bot has the correct permissions in Discord.
- **Logging Errors:** Check the log file specified in `LOG_FILE` for details.

## Contributing

Contributions are welcome. Please submit a pull request or open an issue.
