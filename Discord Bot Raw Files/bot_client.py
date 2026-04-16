# bot_client.py
# Discord bot client – handles connection, message editing, and status updates.

import os
import time
import datetime
import json
import discord
from discord.ext import tasks

from constants import MESSAGE_IDS_FILE


class DiscordBotClient(discord.Client):
    def __init__(self, gui, channel_settings=None, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents, *args, **kwargs)
        self.gui = gui
        self.channel_settings = channel_settings or {}
        self.message_ids = {}  # Format: {channel_id: {"message_id": int, "enabled": bool, "guild_name": str, "channel_name": str}}
        self.last_status = None
        self.manual_mode = False
        self.last_update_time = 0
        self.min_update_interval = 30  # Minimum seconds between updates (rate limiting)

        self.load_message_ids()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def load_message_ids(self):
        """Load all message IDs from file."""
        if os.path.exists(MESSAGE_IDS_FILE):
            try:
                with open(MESSAGE_IDS_FILE, 'r') as f:
                    data = json.load(f)
                    # Convert string keys back to int for channel IDs
                    self.message_ids = {int(k): v for k, v in data.items()}
                    self.gui.log_to_console(f"✅ Loaded {len(self.message_ids)} message ID(s)")
                    for channel_id, info in self.message_ids.items():
                        self.gui.log_to_console(f"  • Channel {channel_id}: Message {info.get('message_id')} (Enabled: {info.get('enabled', True)})")
            except Exception as e:
                self.gui.log_to_console(f"❌ Error loading message IDs: {e}")
                self.message_ids = {}
        else:
            self.gui.log_to_console("📝 No saved message IDs file found")

    def save_message_ids(self):
        """Save all message IDs to file."""
        try:
            with open(MESSAGE_IDS_FILE, 'w') as f:
                # Convert int keys to string for JSON serialization
                json.dump({str(k): v for k, v in self.message_ids.items()}, f, indent=4)
            self.gui.log_to_console(f"💾 Saved {len(self.message_ids)} message ID(s)")
        except Exception as e:
            self.gui.log_to_console(f"❌ Error saving message IDs: {e}")

    def add_or_update_message_id(self, channel_id, message_id, enabled=True, channel_name="", guild_name=""):
        """Add or update a message ID for a channel."""
        self.message_ids[channel_id] = {
            "message_id": message_id,
            "enabled": enabled,
            "channel_name": channel_name,
            "guild_name": guild_name,
            "last_updated": datetime.datetime.now().isoformat()
        }
        self.save_message_ids()
        return True

    def remove_message_id(self, channel_id):
        """Remove a message ID for a channel."""
        if channel_id in self.message_ids:
            del self.message_ids[channel_id]
            self.save_message_ids()
            return True
        return False

    def toggle_message_enabled(self, channel_id):
        """Toggle whether a message should be updated."""
        if channel_id in self.message_ids:
            self.message_ids[channel_id]["enabled"] = not self.message_ids[channel_id].get("enabled", True)
            self.save_message_ids()
            return self.message_ids[channel_id]["enabled"]
        return False

    def get_enabled_channels(self):
        """Get all channels where messaging is enabled."""
        return [channel_id for channel_id, info in self.message_ids.items() if info.get("enabled", True)]

    # ------------------------------------------------------------------
    # Discord event handlers
    # ------------------------------------------------------------------

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        self.gui.update_status("Connected", True)
        self.gui.update_guild_list(self.guilds)
        self.gui.log_to_console(f"✅ Bot connected as {self.user}")

        await self.update_channel_info()
        await self.refresh_message_info()  # Update channel/guild names for existing messages

        interval_minutes = self.gui.update_interval_var.get()
        self.check_message_task.change_interval(seconds=interval_minutes * 60)
        self.check_message_task.start()
        self.gui.log_to_console(f"Status update task started (interval: {interval_minutes} minutes)")

        self.gui.update_manual_mode_display()
        self.gui.update_message_list_display()  # Update the GUI list

        # Initial status update
        await self.update_status_messages()

    async def on_guild_join(self, guild):
        self.gui.update_guild_list(self.guilds)

    async def on_guild_remove(self, guild):
        self.gui.update_guild_list(self.guilds)

    # ------------------------------------------------------------------
    # Channel info
    # ------------------------------------------------------------------

    async def update_channel_info(self):
        """Update channel names and guild information."""
        updated = False
        for guild in self.guilds:
            for channel in guild.text_channels:
                channel_id = str(channel.id)
                if channel_id in self.channel_settings:
                    old_name = self.channel_settings[channel_id].get('name', 'Unknown')
                    old_guild = self.channel_settings[channel_id].get('guild', 'Unknown')

                    self.channel_settings[channel_id]['name'] = channel.name
                    self.channel_settings[channel_id]['guild'] = guild.name

                    if old_name != channel.name or old_guild != guild.name:
                        updated = True
                        self.gui.log_to_console(
                            f"Updated channel {channel_id}: {guild.name}#{channel.name}"
                        )

        if updated and self.gui:
            self.gui.update_channel_tree()

    async def refresh_message_info(self):
        """Refresh guild and channel names for stored message IDs."""
        for channel_id in list(self.message_ids.keys()):
            channel = self.get_channel(channel_id)
            if channel:
                self.message_ids[channel_id]["channel_name"] = channel.name
                self.message_ids[channel_id]["guild_name"] = channel.guild.name
            else:
                self.gui.log_to_console(f"⚠️ Could not find channel {channel_id} for message info")
        self.save_message_ids()
        if self.gui:
            self.gui.update_message_list_display()

    # ------------------------------------------------------------------
    # Status message management
    # ------------------------------------------------------------------

    @tasks.loop(seconds=60)  # Default – overridden in on_ready
    async def check_message_task(self):
        await self.update_status_messages()

    async def update_status_messages(self):
        """Update all enabled status messages."""
        current_time = time.time()
        if current_time - self.last_update_time < self.min_update_interval:
            return

        current_game = self.gui.current_game_var.get()
        game_id = self.gui.game_id_var.get()
        server_active = self.gui.is_server_running()
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        server_emoji = "✅" if server_active else "❌"
        
        # Get the update interval from GUI - make sure it's an integer
        try:
            update_interval_minutes = self.gui.update_interval_var.get()
            if update_interval_minutes == 1:
                update_interval_text = "1 minute"
            else:
                update_interval_text = f"{update_interval_minutes} minutes"
        except Exception:
            update_interval_text = "5 minutes"  # Default fallback

        # Build the message with interval included
        message = (
            f"**Last Check In Time:** {current_time_str}\n\n"
            f"**GameServer:** {'Active' if server_active else 'Inactive'} {server_emoji}\n\n"
            f"**Current Game:** {current_game}\n\n"
            f"**Game ID:** {game_id}\n\n"
            f"**Status Update Interval:** Every {update_interval_text}"
        )

        current_status = (server_active, current_game, game_id, update_interval_minutes)
        if self.last_status != current_status:
            self.gui.log_to_console("Status changed - Updating messages")
            self.last_status = current_status

        manual_mode = self.gui.manual_control_mode.get() if hasattr(self.gui, 'manual_control_mode') else False

        updated_count = 0
        failed_count = 0

        for channel_id, msg_info in self.message_ids.items():
            if not msg_info.get("enabled", True):
                continue

            try:
                channel = self.get_channel(channel_id)
                if not channel:
                    self.gui.log_to_console(f"⚠️ Could not find channel {channel_id} for message update")
                    continue

                if manual_mode:
                    if msg_info.get("message_id"):
                        try:
                            msg = await channel.fetch_message(msg_info["message_id"])
                            await msg.edit(content=message)
                            updated_count += 1
                            self.gui.log_to_console(f"✅ Updated message in channel {channel_id}")
                        except Exception as e:
                            self.gui.log_to_console(f"❌ Could not update message in channel {channel_id}: {e}")
                            failed_count += 1
                else:
                    if msg_info.get("message_id"):
                        try:
                            msg = await channel.fetch_message(msg_info["message_id"])
                            await msg.edit(content=message)
                            updated_count += 1
                            self.gui.log_to_console(f"✅ Updated message in channel {channel_id}")
                        except Exception:
                            self.gui.log_to_console(f"Message {msg_info['message_id']} not found in channel {channel_id}, creating new")
                            msg = await channel.send(message)
                            msg_info["message_id"] = msg.id
                            msg_info["last_updated"] = datetime.datetime.now().isoformat()
                            self.save_message_ids()
                            updated_count += 1
                    else:
                        self.gui.log_to_console(f"No message ID for channel {channel_id}, creating new")
                        msg = await channel.send(message)
                        msg_info["message_id"] = msg.id
                        msg_info["last_updated"] = datetime.datetime.now().isoformat()
                        self.save_message_ids()
                        updated_count += 1

            except Exception as e:
                self.gui.log_to_console(f"Error updating status message in channel {channel_id}: {e}")
                failed_count += 1

        if updated_count > 0 or failed_count > 0:
            self.gui.log_to_console(f"📊 Status update complete: {updated_count} updated, {failed_count} failed")
            self.last_update_time = current_time

        if self.gui:
            self.gui.update_message_list_display()

    async def force_status_update(self):
        """Force an immediate status update."""
        
        # Reset the last update time to bypass rate limiting
        self.last_update_time = 0
        
        # Call the update method directly
        await self.update_status_messages()

    async def create_new_message(self, channel_id, enabled=True):
        """Manually create a new message in a specific channel."""
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                return None

            current_game = self.gui.current_game_var.get()
            game_id = self.gui.game_id_var.get()
            server_active = self.gui.is_server_running()
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            server_emoji = "✅" if server_active else "❌"
            
            # Get the update interval from GUI
            try:
                update_interval_minutes = self.gui.update_interval_var.get()
                if update_interval_minutes == 1:
                    update_interval_text = "1 minute"
                else:
                    update_interval_text = f"{update_interval_minutes} minutes"
            except Exception:
                update_interval_text = "5 minutes"

            message = (
                f"**Last Check In Time:** {current_time_str}\n\n"
                f"**GameServer:** {'Active' if server_active else 'Inactive'} {server_emoji}\n\n"
                f"**Current Game:** {current_game}\n\n"
                f"**Game ID:** {game_id}\n\n"
                f"**Status Update Interval:** Every {update_interval_text}"
            )

            msg = await channel.send(message)
            self.add_or_update_message_id(
                channel_id, 
                msg.id, 
                enabled,
                channel.name,
                channel.guild.name
            )
            self.gui.log_to_console(f"✅ Created new message in channel {channel_id} with ID: {msg.id}")
            return msg.id
        except Exception as e:
            self.gui.log_to_console(f"Error creating message in channel {channel_id}: {e}")
            return None

    async def update_status_messages(self):
        """Update all enabled status messages."""
        current_time = time.time()
        
        if current_time - self.last_update_time < self.min_update_interval:
            return

        current_game = self.gui.current_game_var.get()
        game_id = self.gui.game_id_var.get()
        server_active = self.gui.is_server_running()
        current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        server_emoji = "✅" if server_active else "❌"
        
        # Get the update interval from GUI
        try:
            update_interval_minutes = self.gui.update_interval_var.get()
            if update_interval_minutes == 1:
                update_interval_text = "1 minute"
            else:
                update_interval_text = f"{update_interval_minutes} minutes"
        except Exception:
            update_interval_text = "5 minutes"

        message = (
            f"**Last Check In Time:** {current_time_str}\n\n"
            f"**GameServer:** {'Active' if server_active else 'Inactive'} {server_emoji}\n\n"
            f"**Current Game:** {current_game}\n\n"
            f"**Game ID:** {game_id}\n\n"
            f"**Status Update Interval:** Every {update_interval_text}"
        )

        current_status = (server_active, current_game, game_id, update_interval_minutes)
        if self.last_status != current_status:
            self.last_status = current_status

        manual_mode = self.gui.manual_control_mode.get() if hasattr(self.gui, 'manual_control_mode') else False
        
        updated_count = 0
        failed_count = 0

        for channel_id, msg_info in self.message_ids.items():
            if not msg_info.get("enabled", True):
                self.gui.log_to_console(f"Skipping channel {channel_id} - not enabled")
                continue

            self.gui.log_to_console(f"Processing channel {channel_id}, message_id: {msg_info.get('message_id')}")

            try:
                channel = self.get_channel(channel_id)
                if not channel:
                    self.gui.log_to_console(f"⚠️ Could not find channel {channel_id} for message update")
                    continue

                if manual_mode:
                    if msg_info.get("message_id"):
                        try:
                            msg = await channel.fetch_message(msg_info["message_id"])
                            await msg.edit(content=message)
                            updated_count += 1
                            self.gui.log_to_console(f"✅ Updated message in channel {channel_id}")
                        except Exception as e:
                            self.gui.log_to_console(f"❌ Could not update message in channel {channel_id}: {e}")
                            failed_count += 1
                    else:
                        self.gui.log_to_console(f"No message ID for channel {channel_id} in manual mode - skipping")
                else:
                    if msg_info.get("message_id"):
                        try:
                            msg = await channel.fetch_message(msg_info["message_id"])
                            await msg.edit(content=message)
                            updated_count += 1
                            self.gui.log_to_console(f"✅ Updated message in channel {channel_id}")
                        except Exception as e:
                            self.gui.log_to_console(f"Message {msg_info['message_id']} not found in channel {channel_id}, creating new. Error: {e}")
                            msg = await channel.send(message)
                            msg_info["message_id"] = msg.id
                            msg_info["last_updated"] = datetime.datetime.now().isoformat()
                            self.save_message_ids()
                            updated_count += 1
                            self.gui.log_to_console(f"✅ Created new message in channel {channel_id} with ID: {msg.id}")
                    else:
                        self.gui.log_to_console(f"No message ID for channel {channel_id}, creating new")
                        msg = await channel.send(message)
                        msg_info["message_id"] = msg.id
                        msg_info["last_updated"] = datetime.datetime.now().isoformat()
                        self.save_message_ids()
                        updated_count += 1
                        self.gui.log_to_console(f"✅ Created new message in channel {channel_id} with ID: {msg.id}")

            except Exception as e:
                self.gui.log_to_console(f"Error updating status message in channel {channel_id}: {e}")
                failed_count += 1

        if updated_count > 0 or failed_count > 0:
            self.gui.log_to_console(f"📊 Status update complete: {updated_count} updated, {failed_count} failed")
            self.last_update_time = current_time
        else:
            self.gui.log_to_console("⚠️ No messages were updated")

        if self.gui:
            self.gui.update_message_list_display()