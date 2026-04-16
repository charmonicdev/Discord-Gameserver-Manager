# Discord-Game Server Bot

A powerful GUI application that integrates a Discord bot with game server management. Monitor your game server status, send automatic updates to Discord channels, and control your server all from one interface.

## Features

### Discord Bot Integration
- Connect your Discord bot with a simple token
- Auto-connect on startup option
- Encrypted token storage for security
- Multi-channel support for status messages
- Manual and Auto message control modes

### Game Server Management
- Start/Stop game servers with one click
- Auto-start server when bot connects
- Auto-restart on crash (configurable attempts)
- Server process detection and monitoring
- Attach to existing running servers
- Real-time server status display

### Multi-Message Management
- Create separate status messages for each Discord channel
- Enable/disable individual messages
- Manual message ID entry for existing messages
- Right-click context menu for quick actions
- Update single or all messages at once

### Security Features
- Token encryption with obfuscated key storage
- Machine-specific key validation
- Multiple backup key locations
- Save token option (encrypted)

### Status Information
- Current game name
- Game ID
- Server active/inactive status
- Last check-in time
- Configurable update interval (1-60 minutes)

### User Interface
- Clean tabbed interface
- Real-time console output
- Server list viewer
- Channel management
- Backup management for console logs

## Requirements

- Python 3.8 or higher
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- Supported game server (Core Keeper, etc.)

## Installation

### 1. Clone or Download the Files

Download all files to a folder on your computer.

### 2. Install Required Python Packages

Open a terminal/command prompt in the application folder and run:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install discord.py psutil cryptography
```

### 3. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" tab
4. Click "Add Bot"
5. Copy the bot token (you'll need this later)
6. Enable these Privileged Gateway Intents:
   - Server Members Intent
   - Message Content Intent

### 4. Invite Bot to Your Server

1. In the Developer Portal, go to "OAuth2" → "URL Generator"
2. Select scopes: `bot`
3. Select permissions: `Send Messages`, `Read Messages`, `Read Message History`
4. Copy the generated URL and open it in your browser
5. Select your server and invite the bot

## Configuration

### First-Time Setup

1. Run `main.py` to start the application
2. Go to the **Control** tab
3. Enter your Discord bot token
4. Check "Save Token" if you want to save it (encrypted)
5. Click "Connect"

### Setting Up Game Server

1. In the **Control** tab, under "Game Server Control":
2. Click "Browse" to select your server `.bat` or `.ps1` file
3. Enter the exact process name (e.g., `CoreKeeperServer.exe`)
4. Click "Scan Now" to verify the process name
5. Enable "Auto-start server" if desired
6. Enable "Auto-restart on crash" for automatic recovery

### Adding Discord Channels

1. Go to the **Channels** tab
2. Enable Developer Mode in Discord settings
3. Right-click on a text channel → "Copy ID"
4. Paste the Channel ID and click "Add Channel"
5. Click on the checkbox in the tree to enable/disable channels

### Creating Status Messages

1. Go to the **Messages** tab
2. Select a channel (⚪ indicates no message yet)
3. Click "Create New" or right-click for options
4. Choose to either:
   - **Add Manual ID**: Paste an existing Discord message ID
   - **Create New Message**: Let the bot create a fresh message
5. The message will automatically update based on your settings

## Usage Guide

### Control Tab

| Element | Description |
|---------|-------------|
| Token | Your Discord bot token |
| Save Token | Encrypt and save token locally |
| Auto-connect | Automatically connect bot on startup |
| Connect/Disconnect | Manual bot connection control |
| Server File | Path to your server launcher |
| Process Name | Name of the server executable |
| Scan Now | Verify process name is correct |
| Auto-start | Launch server when bot connects |
| Auto-restart | Automatically restart on crash |
| Start/Kill Server | Manual server control |

### Settings Tab

| Setting | Description |
|---------|-------------|
| Current Game | Name of the game being played |
| Game ID | Server/game identifier |
| Logging Control | Enable/disable console logging |
| Update Interval | How often Discord messages update (minutes) |
| Security | Encryption status and verification |

### Messages Tab

| Status | Meaning |
|--------|---------|
| ⚪ | No message yet - needs to be created |
| ✅ | Message exists and is enabled |
| ❌ | Message exists but is disabled |

**Right-click options:**
- Add Manual Message ID
- Create New Message
- Update Message
- Remove Message

### Message Control Tab

| Mode | Behavior |
|------|----------|
| Auto Mode | Bot automatically creates missing messages |
| Manual Mode | Bot only updates existing messages (never creates) |

## File Structure

```
├── main.py                 # Application entry point
├── gui.py                  # Main GUI interface
├── bot_client.py           # Discord bot functionality
├── server_manager.py       # Game server management
├── encryption_manager.py   # Token encryption
├── constants.py            # Configuration constants
└── requirements.txt        # Python dependencies
```

## Auto-Generated Files

| File | Purpose |
|------|---------|
| `bot_config.json` | Saved configuration (encrypted token) |
| `message_ids.json` | Stored message IDs per channel |
| `logging_config.json` | Logging on/off state |
| `system_metrics_cache.dat` | Encrypted key storage (obfuscated) |
| `.app_preferences.bin` | Backup key storage (hidden) |
| `temp_thumbnails.db` | Key metadata storage |
| `console_backups/` | Console log backups |

## Troubleshooting

### Bot Won't Connect
- Verify your token is correct
- Check that bot has proper intents enabled
- Ensure bot is invited to your server

### Server Not Detected
- Verify the process name exactly matches (case-sensitive)
- Click "Scan Now" to find the correct name
- Check if server is actually running

### Messages Not Updating
- Verify channel is enabled in Channels tab
- Check that a message exists (⚪ status)
- Try manual update via right-click
- Check console for error messages

### Token Save Failed
- Check write permissions in the application folder
- Encryption keys may be corrupted - use "Verify Key Integrity"

### Permission Denied Errors
- Run application as administrator (Windows)
- Check folder permissions
- Disable antivirus temporarily

## Security Notes

- Bot tokens are encrypted before saving
- Encryption keys are obfuscated with misleading filenames
- Keys are machine-specific for additional security
- **IMPORTANT**: Back up the key files if you want to recover saved tokens
- Never share your `bot_config.json` or key files

## Tips

1. **Auto Mode** is best for most users - it handles message creation automatically
2. **Manual Mode** gives you full control over when messages are created
3. Use **Update Interval** to control Discord rate limits (5 minutes is recommended)
4. Enable **Auto-restart** to keep your server running reliably
5. Console backups are automatically created - they're saved in `console_backups/`

## License

This software is provided as-is for personal use.

## Support

For issues or feature requests, check the console output for error messages and ensure all requirements are properly installed.

---

