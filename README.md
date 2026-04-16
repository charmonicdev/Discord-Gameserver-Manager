```markdown
# Discord-Game Server Bot

A powerful GUI application that integrates a Discord bot with game server management. Monitor your game server status and send automatic updates to Discord channels - all from one interface.

Includes a .exe for anyone who does not want to buid their own. Located in /Deployable

## Features

- Discord Bot Integration - Connect your Discord bot with encrypted token storage
- Game Server Control - Start/stop servers, auto-restart on crash, attach to existing instances
- Multi-Channel Messages - Create separate status messages for each Discord channel
- Real-time Updates - Configurable update intervals (1-60 minutes)
- Security - Token encryption with obfuscated key storage
- Clean GUI - Tabbed interface with console output and server management

## Quick Start

### Prerequisites
- Python 3.8+
- Discord Bot Token (Get one from Discord Developer Portal)

### Installation

```bash
git clone https://github.com/yourusername/discord-game-server-bot.git
cd discord-game-server-bot
pip install -r requirements.txt
python main.py
```

### First Time Setup

1. Enter your Discord bot token and click "Connect"
2. Add your server's .bat or .ps1 file path
3. Enter the server process name (e.g., CoreKeeperServer.exe)
4. Add Discord channel IDs in the Channels tab
5. Create status messages in the Messages tab

## File Structure

```
├── main.py                 # Application entry point
├── gui.py                  # GUI interface
├── bot_client.py           # Discord bot logic
├── server_manager.py       # Server process management
├── encryption_manager.py   # Token encryption
└── constants.py            # Configuration constants
```

## Usage

| Tab | Purpose |
|-----|---------|
| Control | Bot connection & server control |
| Settings | Game info, logging, update interval |
| Channels | Add/manage Discord channels |
| Messages | Create/update status messages |
| Message Control | Auto vs Manual mode |
| Servers | View Discord servers |
| Console | Real-time logs |

## Configuration

All settings are auto-saved. Key files created:
- bot_config.json - Encrypted bot settings
- message_ids.json - Stored message IDs
- system_metrics_cache.dat - Obfuscated encryption keys

## Building Executable

```bash
pip install auto-py-to-exe
auto-py-to-exe
```

Select main.py -> One File -> Convert

## Requirements

```
discord.py>=2.3.0
psutil>=5.9.0
cryptography>=41.0.0
```

## Contributing

Issues and pull requests welcome.

## License

MIT

Made for Core Keeper and other game servers
```

```
A GUI application that combines a Discord bot with game server management. Monitor server status, send automatic updates to Discord, control multiple channels, and manage your game server - all from one interface. Supports Core Keeper and other game servers.
```

tags:
```
discord-bot, game-server, server-monitor, core-keeper, tkinter, discord-py, server-management, gui-application
```
