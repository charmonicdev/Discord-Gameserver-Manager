# gui.py
# Builds every tab in the tkinter notebook and owns all GUI-level event handlers.
# Logic that touches Discord or the OS lives in bot_client.py / server_manager.py.

import asyncio
import datetime
import json
import os

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

from constants import (
    CONFIG_FILE, CURRENT_GAME_FILE, GAME_ID_FILE_PATH,
    MESSAGE_IDS_FILE, CONSOLE_BACKUP_DIR, CONSOLE_BACKUP_HOURS,
    KEY_FILE, KEY_BACKUP_FILE, KEY_METADATA_FILE, LOGGING_CONFIG_FILE
)
from encryption_manager import EncryptionManager


class BotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Discord-Game Server Bot")
        self.root.geometry("900x900")
        
        # Initialize encryption manager
        self.encryption_manager = EncryptionManager()

        # --- tk variables ---
        self.token_var = tk.StringVar()
        self.auto_connect_var = tk.BooleanVar()
        self.auto_start_server_var = tk.BooleanVar()
        self.auto_restart_server_var = tk.BooleanVar(value=True)
        self.current_game_var = tk.StringVar()
        self.game_id_var = tk.StringVar()
        self.server_file_path = tk.StringVar()
        self.process_name_var = tk.StringVar(value="CoreKeeperServer.exe")
        self.game_id_file_path = tk.StringVar()
        self.update_interval_var = tk.IntVar(value=5)
        self.save_token_var = tk.BooleanVar(value=False)
        self.channel_var = tk.StringVar()
        self.manual_message_id_var = tk.StringVar()
        self.manual_control_mode = tk.BooleanVar(value=False)
        
        # Initialize logging control BEFORE creating widgets
        self.logging_enabled_var = tk.BooleanVar(value=True)

        # --- runtime state (populated by ServerManager mixin) ---
        self.channel_settings = {}
        self.bot_thread = None
        self.bot_client = None
        self.bot_loop = None
        self.server_process = None
        self.launcher_process = None
        self.server_monitor_thread = None
        self.server_monitor_running = False
        self.last_server_status = None
        self.restart_attempts = 0
        self.max_restart_attempts = 3
        self.is_killing = False
        self.startup_grace_period = 30
        self.startup_time = 0
        self.last_console_clear = datetime.datetime.now()
        self.server_status_label = None  # Will be set in create_main_tab

        if not os.path.exists(CONSOLE_BACKUP_DIR):
            os.makedirs(CONSOLE_BACKUP_DIR)

        self.create_widgets()

        self.load_config()
        self.load_current_game()
        self.load_current_message_id_display()
        self.load_logging_config()
        self.update_logging_ui()

        self.log_to_console("🚀 Bot GUI initialized")
        self.log_to_console(f"Auto-connect: {self.auto_connect_var.get()}")
        self.log_to_console(f"Auto-start server: {self.auto_start_server_var.get()}")

        self.schedule_console_cleanup()

        if self.auto_connect_var.get():
            self.log_to_console("Auto-connect enabled - connecting in 1 second...")
            self.root.after(1000, self.connect_bot)

    # ================================================================
    # Status indicators (defined early to avoid AttributeError)
    # ================================================================

    def _update_status_indicator(self, active):
        """Update the status indicator circle."""
        if hasattr(self, 'status_indicator'):
            self.status_indicator.delete("all")
            color = "green" if active else "red"
            self.status_indicator.create_oval(2, 2, 18, 18, fill=color, outline="")

    def update_status(self, status_text, is_active):
        self.status_label.config(text=status_text)
        self._update_status_indicator(is_active)
        self.log_to_console(f"Bot status changed to: {status_text}")
        if is_active:
            self.connect_button.config(state='disabled')
            self.disconnect_button.config(state='normal')
        else:
            self.connect_button.config(state='normal')
            self.disconnect_button.config(state='disabled')

    # ================================================================
    # Widget construction
    # ================================================================

    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text='Control')

        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text='Settings')

        channels_frame = ttk.Frame(notebook)
        notebook.add(channels_frame, text='Channels')
        
        messages_frame = ttk.Frame(notebook)
        notebook.add(messages_frame, text='Messages')

        manual_frame = ttk.Frame(notebook)
        notebook.add(manual_frame, text='Message Control')

        servers_frame = ttk.Frame(notebook)
        notebook.add(servers_frame, text='Servers')

        console_frame = ttk.Frame(notebook)
        notebook.add(console_frame, text='Console')

        self.create_main_tab(main_frame)
        self.create_settings_tab(settings_frame)
        self.create_channels_tab(channels_frame)
        self.create_messages_tab(messages_frame)
        self.create_manual_control_tab(manual_frame)
        self.create_servers_tab(servers_frame)
        self.create_console_tab(console_frame)

    # ------------------------------------------------------------------ Control tab

    def create_main_tab(self, parent):
        status_frame = ttk.LabelFrame(parent, text="Discord Bot Status", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)

        self.status_label = ttk.Label(status_frame, text="Inactive", font=('Arial', 12, 'bold'))
        self.status_label.pack(side='left', padx=5)

        self.status_indicator = tk.Canvas(status_frame, width=20, height=20)
        self.status_indicator.pack(side='left', padx=5)
        self._update_status_indicator(False)

        control_frame = ttk.LabelFrame(parent, text="Discord Bot Launcher", padding=10)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(control_frame, text="Token:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(control_frame, textvariable=self.token_var, width=40, show="*").grid(
            row=0, column=1, padx=5, pady=5)

        ttk.Checkbutton(control_frame, text="Save Token",
                        variable=self.save_token_var,
                        command=self.save_config).grid(
            row=1, column=0, columnspan=2, sticky='w', pady=5)

        ttk.Checkbutton(control_frame, text="Auto-connect on startup",
                        variable=self.auto_connect_var,
                        command=self.save_config).grid(
            row=2, column=0, columnspan=2, sticky='w', pady=5)

        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)

        self.connect_button = ttk.Button(button_frame, text="Connect", command=self.connect_bot)
        self.connect_button.pack(side='left', padx=5)

        self.disconnect_button = ttk.Button(button_frame, text="Disconnect",
                                            command=self.disconnect_bot, state='disabled')
        self.disconnect_button.pack(side='left', padx=5)

        server_frame = ttk.LabelFrame(parent, text="Game Server Control", padding=10)
        server_frame.pack(fill='x', padx=10, pady=5)   

        # Row 0: Server File
        ttk.Label(server_frame, text="Server File:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(server_frame, textvariable=self.server_file_path, width=30).grid(
            row=0, column=1, padx=5, pady=5)
        ttk.Button(server_frame, text="Browse",
                   command=self.browse_server_file).grid(row=0, column=2, padx=5, pady=5)

        # Row 1: Process Name
        ttk.Label(server_frame, text="Process Name:").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(server_frame, textvariable=self.process_name_var, width=30).grid(
            row=1, column=1, padx=5, pady=5, sticky='w')
        ttk.Button(server_frame, text="Scan Now",
                   command=self.scan_for_process).grid(row=1, column=2, padx=5, pady=5)

        # Row 2: Auto-start checkbox
        ttk.Checkbutton(server_frame, text="Auto-start server (launches when bot connects)",
                        variable=self.auto_start_server_var,
                        command=self.save_config).grid(
            row=2, column=0, columnspan=3, sticky='w', pady=5)

        # Row 3: Auto-restart checkbox
        ttk.Checkbutton(server_frame, text="Auto-restart on crash (max 3 attempts)",
                        variable=self.auto_restart_server_var,
                        command=self.save_config).grid(
            row=3, column=0, columnspan=3, sticky='w', pady=5)

        # Row 4: PID Frame
        pid_frame = ttk.Frame(server_frame)
        pid_frame.grid(row=4, column=0, columnspan=3, sticky='w', pady=5)

        ttk.Label(pid_frame, text="Launcher PID:").pack(side='left', padx=(0, 5))
        self.launcher_pid_label = ttk.Label(pid_frame, text="Not running", foreground="gray")
        self.launcher_pid_label.pack(side='left', padx=(0, 15))

        ttk.Label(pid_frame, text="Server PID:").pack(side='left', padx=(0, 5))
        self.server_pid_label = ttk.Label(pid_frame, text="Not found", foreground="gray")
        self.server_pid_label.pack(side='left')
        
        # Row 5: Server Status Label
        status_row_frame = ttk.Frame(server_frame)
        status_row_frame.grid(row=5, column=0, columnspan=3, sticky='w', pady=(5, 0))
        
        ttk.Label(status_row_frame, text="Server Status:", font=('Arial', 9, 'bold')).pack(side='left', padx=(0, 5))
        self.server_status_label = ttk.Label(status_row_frame, text="⚫ Stopped", foreground="gray", font=('Arial', 9))
        self.server_status_label.pack(side='left')
        
        # Row 6: Separator
        ttk.Separator(server_frame, orient='horizontal').grid(row=6, column=0, columnspan=3, sticky='ew', pady=10)
        
        # Row 7: Info panel (moved to bottom)
        info_text_frame = ttk.Frame(server_frame)
        info_text_frame.grid(row=7, column=0, columnspan=3, sticky='w', pady=(0, 5))
        
        info_label = ttk.Label(
            info_text_frame,
            text="ℹ️ Setup Guide:\n"
                 "   1. Browse to select your server .bat or .ps1 file\n"
                 "   2. Enter the exact process name (e.g., CoreKeeperServer.exe)\n"
                 "   3. Click 'Scan Now' to verify the process name is correct\n"
                 "   4. Enable 'Auto-start server' to launch with bot connection\n"
                 "   5. Enable 'Auto-restart on crash' for automatic recovery\n\n"
                 "📌 Note: The server might run in a separate window. Use 'Kill Server' to stop it.\n"
                 "🔄 Status indicator shows: ⚫ Stopped | 🟡 Starting | 🟢 Running | 🔴 Crashed",
            font=("TkDefaultFont", 8),
            foreground="gray",
            justify='left'
        )
        info_label.pack(anchor='w')
        
        # Row 8: Button Frame
        server_button_frame = ttk.Frame(server_frame)
        server_button_frame.grid(row=8, column=0, columnspan=3, pady=10)

        self.start_server_button = ttk.Button(server_button_frame, text="Start Server",
                                              command=self.start_server)
        self.start_server_button.pack(side='left', padx=5)

        self.kill_server_button = ttk.Button(server_button_frame, text="Kill Server",
                                             command=self.kill_server, state='disabled')
        self.kill_server_button.pack(side='left', padx=5)
        
        


    # ------------------------------------------------------------------ Settings tab

    def create_settings_tab(self, parent):
        game_frame = ttk.LabelFrame(parent, text="Game Settings", padding=10)
        game_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(game_frame, text="Current Game:").grid(row=0, column=0, sticky='w', pady=5)
        current_game_entry = ttk.Entry(game_frame, textvariable=self.current_game_var, width=40)
        current_game_entry.grid(row=0, column=1, padx=5, pady=5)
        current_game_entry.bind('<FocusOut>', lambda e: self.save_current_game())
        current_game_entry.bind('<Return>', lambda e: self.save_current_game())
        
        ttk.Label(game_frame, text="Game ID:").grid(row=1, column=0, sticky='w', pady=5)
        game_id_entry = ttk.Entry(game_frame, textvariable=self.game_id_var, width=40)
        game_id_entry.grid(row=1, column=1, padx=5, pady=5)
        game_id_entry.bind('<FocusOut>', lambda e: self.save_game_id())
        game_id_entry.bind('<Return>', lambda e: self.save_game_id())
        
        logging_frame = ttk.LabelFrame(parent, text="Logging Control", padding=10)
        logging_frame.pack(fill='x', padx=10, pady=5)
        
        button_frame = ttk.Frame(logging_frame)
        button_frame.pack(fill='x', pady=5)
        
        self.logging_toggle_button = ttk.Button(
            button_frame, 
            text="Disable Logging" if self.logging_enabled_var.get() else "Enable Logging",
            command=self.toggle_logging,
            width=15
        )
        self.logging_toggle_button.pack(side='left', padx=5)
        
        status_text = "Enabled ✓" if self.logging_enabled_var.get() else "Disabled ✗"
        self.logging_status_label = ttk.Label(
            button_frame, 
            text=f"Status: {status_text}",
            foreground="green" if self.logging_enabled_var.get() else "red"
        )
        self.logging_status_label.pack(side='left', padx=10)
        
        ttk.Label(
            logging_frame,
            text="Toggle console logging on/off. Settings save automatically when clicked.",
            font=("TkDefaultFont", 8),
            foreground="gray"
        ).pack(anchor='w', pady=(5, 0))
        
        interval_frame = ttk.LabelFrame(parent, text="Update Settings", padding=10)
        interval_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(interval_frame, text="Status Update Interval (minutes):").grid(
            row=0, column=0, sticky='w', pady=5)
        interval_spinbox = ttk.Spinbox(interval_frame, from_=1, to=60,
                    textvariable=self.update_interval_var, width=10)
        interval_spinbox.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        interval_spinbox.bind('<FocusOut>', lambda e: self.apply_update_interval())
        interval_spinbox.bind('<Return>', lambda e: self.apply_update_interval())
        
        ttk.Label(interval_frame,
                  text="Status will also update immediately when server status changes",
                  font=("TkDefaultFont", 8), foreground="gray").grid(
            row=1, column=0, columnspan=3, sticky='w', pady=5)
        
        security_frame = ttk.LabelFrame(parent, text="Security", padding=10)
        security_frame.pack(fill='x', padx=10, pady=5)

        if self.encryption_manager.is_key_available():
            status_text = "✅ Token Encryption: ENABLED (Obfuscated)"
            status_color = "green"
            key_status = "Key storage: system_metrics_cache.dat (obfuscated)"
        else:
            status_text = "❌ Token Encryption: DISABLED"
            status_color = "red"
            key_status = "Encryption not available"
        
        ttk.Label(security_frame, text=status_text, foreground=status_color, 
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=2)
        ttk.Label(security_frame, text=key_status, font=("TkDefaultFont", 8), 
                  foreground="gray").pack(anchor='w', pady=2)
        
        verify_button = ttk.Button(security_frame, text="Verify Key Integrity", 
                                   command=self.verify_encryption_integrity)
        verify_button.pack(anchor='w', pady=(5, 0))

    # ------------------------------------------------------------------ Channels tab

    def create_channels_tab(self, parent):
        channel_frame = ttk.LabelFrame(parent, text="Channel Management", padding=5)
        channel_frame.pack(fill='both', expand=True, padx=10, pady=5)
        channel_frame.columnconfigure(1, weight=1)

        ttk.Label(channel_frame, text="Channel ID:").grid(
            row=0, column=0, sticky=tk.W, pady=2, padx=(0, 5))
        self.channel_entry = ttk.Entry(channel_frame, textvariable=self.channel_var, width=30)
        self.channel_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=(0, 5))

        channel_buttons_frame = ttk.Frame(channel_frame)
        channel_buttons_frame.grid(row=0, column=2, padx=(0, 0), pady=2)

        ttk.Button(channel_buttons_frame, text="Add Channel",
                   command=self.add_channel).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(channel_buttons_frame, text="Remove Selected",
                   command=self.remove_channel).pack(side=tk.LEFT)

        ttk.Label(channel_frame,
                  text="Configured Channels (click checkbox to enable/disable):").grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 2))

        tree_frame = ttk.Frame(channel_frame)
        tree_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 2))
        tree_frame.columnconfigure(0, weight=1)

        self.channel_tree = ttk.Treeview(
            tree_frame,
            columns=("status", "server", "channel", "id"),
            show="headings", height=6,
        )
        self.channel_tree.heading("status", text="Enabled")
        self.channel_tree.heading("server", text="Server")
        self.channel_tree.heading("channel", text="Channel")
        self.channel_tree.heading("id", text="Channel ID")
        self.channel_tree.column("status", width=60, anchor="center", minwidth=60)
        self.channel_tree.column("server", width=200, anchor="w", minwidth=150)
        self.channel_tree.column("channel", width=200, anchor="w", minwidth=150)
        self.channel_tree.column("id", width=180, anchor="w", minwidth=150)
        self.channel_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                       command=self.channel_tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.channel_tree.configure(yscrollcommand=tree_scrollbar.set)
        self.channel_tree.bind("<ButtonRelease-1>", self.on_tree_click)

        bulk_frame = ttk.Frame(channel_frame)
        bulk_frame.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(2, 5))

        ttk.Button(bulk_frame, text="Enable All",
                   command=self.enable_all_channels).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bulk_frame, text="Disable All",
                   command=self.disable_all_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(bulk_frame, text="Refresh Channel Info",
                   command=self.refresh_channel_info).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            channel_frame,
            text="To find Channel ID: Right-click on a Discord channel → Copy ID "
                 "(Developer Mode must be enabled)",
            font=("TkDefaultFont", 8), foreground="gray",
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(2, 2))

    # ------------------------------------------------------------------ Messages tab

    def create_messages_tab(self, parent):
        """Create the Messages tab for managing multiple status messages."""
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        info_frame = ttk.LabelFrame(main_frame, text="Status Messages", padding=10)
        info_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(info_frame, text="Manage status messages across multiple channels/servers",
                  font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Label(info_frame,
                  text="⚪ = No message yet | ✅ = Enabled | ❌ = Disabled\n"
                       "• Right-click on a channel for more options\n"
                       "• Use 'Create New' button or right-click to add a message\n"
                       "• Status messages show: Game status, Game ID, and Update Interval",
                  font=("TkDefaultFont", 8), foreground="gray").pack(anchor='w', pady=(5, 0))
        
        list_frame = ttk.LabelFrame(main_frame, text="Channels & Messages", padding=10)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        columns = ('status', 'guild', 'channel', 'message_id', 'last_updated')
        self.message_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        self.message_tree.heading('status', text='Status')
        self.message_tree.heading('guild', text='Server/Guild')
        self.message_tree.heading('channel', text='Channel')
        self.message_tree.heading('message_id', text='Message ID')
        self.message_tree.heading('last_updated', text='Last Updated')
        
        self.message_tree.column('status', width=80, anchor='center')
        self.message_tree.column('guild', width=200)
        self.message_tree.column('channel', width=200)
        self.message_tree.column('message_id', width=200)
        self.message_tree.column('last_updated', width=150)
        
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.message_tree.yview)
        self.message_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.message_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # Bind click and right-click events
        self.message_tree.bind("<ButtonRelease-1>", self.on_message_tree_click)
        self.message_tree.bind("<Button-3>", self.on_message_tree_right_click)
        
        # Create right-click context menu
        self.message_context_menu = tk.Menu(self.message_tree, tearoff=0)
        self.message_context_menu.add_command(label="Add Manual Message ID", command=self.add_manual_id_to_selected)
        self.message_context_menu.add_command(label="Create New Message", command=lambda: self.create_new_message_dialog())
        self.message_context_menu.add_separator()
        self.message_context_menu.add_command(label="Update Message", command=self.update_selected_message)
        self.message_context_menu.add_command(label="Remove Message", command=self.remove_selected_message)
        
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x')
        
        left_buttons = ttk.Frame(control_frame)
        left_buttons.pack(side='left', fill='x', expand=True)
        
        ttk.Button(left_buttons, text="Refresh List", 
                   command=self.refresh_message_list).pack(side='left', padx=5)
        ttk.Button(left_buttons, text="Update Selected", 
                   command=self.update_selected_message).pack(side='left', padx=5)
        ttk.Button(left_buttons, text="Update All", 
                   command=self.update_all_messages).pack(side='left', padx=5)
        
        right_buttons = ttk.Frame(control_frame)
        right_buttons.pack(side='right')
        
        ttk.Button(right_buttons, text="Create New", 
                   command=self.create_new_message_dialog).pack(side='left', padx=5)
        ttk.Button(right_buttons, text="Remove Selected", 
                   command=self.remove_selected_message).pack(side='left', padx=5)
        ttk.Button(right_buttons, text="Enable All", 
                   command=self.enable_all_messages).pack(side='left', padx=5)
        ttk.Button(right_buttons, text="Disable All", 
                   command=self.disable_all_messages).pack(side='left', padx=5)
        
        self.message_status_label = ttk.Label(main_frame, text="", foreground="blue")
        self.message_status_label.pack(pady=(10, 0))

    # ------------------------------------------------------------------ Message Control tab

    def create_manual_control_tab(self, parent):
        manual_frame = ttk.LabelFrame(parent, text="Control Mode", padding=10)
        manual_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(manual_frame, text="Message Control Mode:",
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 10))

        mode_frame = ttk.Frame(manual_frame)
        mode_frame.pack(anchor='w', pady=5)

        self.auto_mode_radio = ttk.Radiobutton(
            mode_frame,
            text="Auto Mode (Bot automatically creates and manages messages)",
            variable=self.manual_control_mode, value=False,
            command=self.on_mode_change,
        )
        self.auto_mode_radio.pack(anchor='w')

        self.manual_mode_radio = ttk.Radiobutton(
            mode_frame,
            text="Manual Mode (You control all messages - bot never auto-creates)",
            variable=self.manual_control_mode, value=True,
            command=self.on_mode_change,
        )
        self.manual_mode_radio.pack(anchor='w', pady=(5, 0))

        self.mode_status_label = ttk.Label(mode_frame, text="", font=('Arial', 9))
        self.mode_status_label.pack(anchor='w', pady=(10, 0))
        
        info_frame = ttk.LabelFrame(parent, text="Information", padding=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        instructions = (
            "📌 Message Management:\n\n"
            "• Use the 'Messages' tab to manage individual status messages\n"
            "• Each channel can have its own status message\n"
            "• Enable/disable messages individually\n"
            "• Update single messages or all at once\n\n"
            "📌 Mode Differences:\n"
            "• AUTO Mode: Bot will create missing messages automatically\n"
            "• MANUAL Mode: Bot will only update existing messages, never create new ones"
        )
        ttk.Label(info_frame, text=instructions, justify='left',
                  font=("TkDefaultFont", 9)).pack(anchor='w', pady=5)

    # ------------------------------------------------------------------ Servers tab

    def create_servers_tab(self, parent):
        list_frame = ttk.LabelFrame(parent, text="Servers", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('Name', 'ID', 'Owner', 'Members')
        self.server_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        self.server_tree.heading('Name', text='Server Name')
        self.server_tree.heading('ID', text='Server ID')
        self.server_tree.heading('Owner', text='Owner')
        self.server_tree.heading('Members', text='Members')
        self.server_tree.column('Name', width=250, minwidth=150)
        self.server_tree.column('ID', width=180, minwidth=100)
        self.server_tree.column('Owner', width=180, minwidth=100)
        self.server_tree.column('Members', width=80, minwidth=60, anchor='center')

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical',
                                  command=self.server_tree.yview)
        self.server_tree.configure(yscrollcommand=scrollbar.set)
        self.server_tree.pack(side='left', fill='both', expand=True, padx=(0, 5))
        scrollbar.pack(side='right', fill='y')

        control_frame = ttk.Frame(parent)
        control_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(control_frame, text="Refresh Server List",
                   command=self.refresh_guild_list).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Generate Invite",
                   command=self.generate_invite).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Leave Server",
                   command=self.leave_server).pack(side='left', padx=5)

    # ------------------------------------------------------------------ Console tab

    def create_console_tab(self, parent):
        console_frame = ttk.LabelFrame(parent, text="Console Output", padding=10)
        console_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.console_text = scrolledtext.ScrolledText(console_frame, height=20, wrap=tk.WORD)
        self.console_text.pack(fill='both', expand=True)
        self.console_text.insert(tk.END, "=== Console Initialized ===\n")
        self.console_text.see(tk.END)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(button_frame, text="Clear Console",
                   command=self.clear_console).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Save Backup",
                   command=self.save_manual_backup).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clean Old Backups",
                   command=self.cleanup_old_backups).pack(side='left', padx=5)
        ttk.Button(button_frame, text="List Backups",
                   command=self.list_backups).pack(side='left', padx=5)

    # ================================================================
    # Message management handlers
    # ================================================================

    def on_message_tree_click(self, event):
        """Handle clicks on the message tree to toggle enabled status."""
        region = self.message_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.message_tree.identify_column(event.x)
            if column == "#1":
                item = self.message_tree.identify_row(event.y)
                if item:
                    tags = self.message_tree.item(item, "tags")
                    if tags:
                        channel_id = int(tags[0])
                        has_message = len(tags) > 1 and tags[1]
                        
                        if not has_message and self.bot_client:
                            self.message_status_label.config(
                                text="⚠️ No message exists yet. Use 'Create New' first.",
                                foreground="orange")
                            self.root.after(3000, lambda: self.message_status_label.config(text=""))
                            return
                        
                        if self.bot_client and has_message:
                            new_status = self.bot_client.toggle_message_enabled(channel_id)
                            self.update_message_list_display()
                            self.log_to_console(f"Message for channel {channel_id} {'enabled' if new_status else 'disabled'}")

    def on_message_tree_right_click(self, event):
        """Handle right-click on message tree to show context menu."""
        item = self.message_tree.identify_row(event.y)
        if item:
            self.message_tree.selection_set(item)
            tags = self.message_tree.item(item, "tags")
            has_message = len(tags) > 1 and tags[1] if tags else False
            
            self.message_context_menu.entryconfig("Update Message", state="normal" if has_message else "disabled")
            self.message_context_menu.entryconfig("Remove Message", state="normal" if has_message else "disabled")
            self.message_context_menu.entryconfig("Add Manual Message ID", state="disabled" if has_message else "normal")
            
            self.message_context_menu.post(event.x_root, event.y_root)

    def add_manual_id_to_selected(self):
        """Add a manual message ID to the currently selected channel."""
        selection = self.message_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a channel first")
            return
        
        tags = self.message_tree.item(selection[0], "tags")
        if not tags:
            return
        
        channel_id = int(tags[0])
        has_message = len(tags) > 1 and tags[1]
        
        if has_message:
            messagebox.showinfo("Info", "This channel already has a message. Use 'Create New' to replace it.")
            return
        
        values = self.message_tree.item(selection[0], "values")
        channel_name = f"{values[1]} → #{values[2]}" if len(values) >= 3 else f"Channel {channel_id}"
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Manual Message ID")
        dialog.geometry("450x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Add Message ID for:", font=('Arial', 10, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=channel_name, foreground="blue").pack()
        
        ttk.Label(dialog, text="\nMessage ID:", font=('Arial', 10)).pack(pady=(15, 5))
        msg_id_var = tk.StringVar()
        msg_id_entry = ttk.Entry(dialog, textvariable=msg_id_var, width=35)
        msg_id_entry.pack(pady=5)
        
        ttk.Label(dialog, text="💡 Right-click on any Discord message → Copy ID\n(Enable Developer Mode in Discord settings)", 
                  font=("TkDefaultFont", 8), foreground="gray").pack(pady=10)
        
        enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Enable this message", variable=enabled_var).pack(pady=5)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        
        def add_id():
            msg_id = msg_id_var.get().strip()
            if not msg_id:
                messagebox.showwarning("Warning", "Please enter a message ID")
                return
            if not msg_id.isdigit():
                messagebox.showwarning("Warning", "Message ID must be a number")
                return
            
            async def add_manual_message_async():
                channel = self.bot_client.get_channel(channel_id)
                if channel:
                    success = self.bot_client.add_or_update_message_id(
                        channel_id, 
                        int(msg_id), 
                        enabled_var.get(),
                        channel.name,
                        channel.guild.name
                    )
                    if success:
                        self.root.after(0, lambda: messagebox.showinfo("Success", 
                            f"✅ Message ID added successfully!\n\nChannel: {channel_name}\nMessage ID: {msg_id}"))
                        self.root.after(0, self.update_message_list_display)
                        self.root.after(0, dialog.destroy)
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", "Failed to add message ID"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not find channel"))
            
            asyncio.run_coroutine_threadsafe(add_manual_message_async(), self.bot_loop)
        
        ttk.Button(button_frame, text="Add Message ID", command=add_id).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)
        
        msg_id_entry.focus()

    def update_message_list_display(self):
        """Update the message list treeview with all channels and their message status."""
        for item in self.message_tree.get_children():
            self.message_tree.delete(item)
        
        if not self.channel_settings:
            self.message_tree.insert("", tk.END, values=("", "No channels", "Add channels in Channels tab", "", ""))
            return
        
        channels_list = []
        for channel_id, settings in self.channel_settings.items():
            if settings.get('enabled', False):
                guild_name = settings.get('guild', 'Unknown')
                channel_name = settings.get('name', 'Unknown')
                channels_list.append((channel_id, guild_name, channel_name))
        
        channels_list.sort(key=lambda x: (x[1], x[2]))
        
        message_info = {}
        if self.bot_client and hasattr(self.bot_client, 'message_ids'):
            message_info = self.bot_client.message_ids
        
        for channel_id, guild_name, channel_name in channels_list:
            channel_id_int = int(channel_id)
            msg_info = message_info.get(channel_id_int, {})
            
            has_message = msg_info.get('message_id') is not None
            enabled = msg_info.get('enabled', True) if has_message else False
            message_id = str(msg_info.get('message_id', 'No message')) if has_message else 'No message'
            last_updated = msg_info.get('last_updated', 'Never')[:16] if msg_info.get('last_updated') else 'Never'
            
            if has_message:
                enabled_display = "✅" if enabled else "❌"
            else:
                enabled_display = "⚪"
                message_id = "Click 'Create New' to add"
            
            self.message_tree.insert("", tk.END, 
                                     values=(enabled_display, guild_name, channel_name, message_id, last_updated),
                                     tags=(channel_id, has_message))

    def refresh_message_list(self):
        """Refresh the message list display."""
        if self.bot_client and self.bot_client.is_ready():
            asyncio.run_coroutine_threadsafe(self.bot_client.refresh_message_info(), self.bot_loop)
        self.update_message_list_display()
        
        channels_without_messages = 0
        for channel_id in self.channel_settings:
            if self.channel_settings[channel_id].get('enabled', False):
                if not (self.bot_client and hasattr(self.bot_client, 'message_ids') and 
                        int(channel_id) in self.bot_client.message_ids):
                    channels_without_messages += 1
        
        if channels_without_messages > 0:
            self.message_status_label.config(
                text=f"✅ List refreshed - {channels_without_messages} channel(s) need messages created", 
                foreground="blue")
        else:
            self.message_status_label.config(text="✅ Message list refreshed", foreground="green")
        self.root.after(3000, lambda: self.message_status_label.config(text=""))

    def update_selected_message(self):
        """Update the selected message."""
        selection = self.message_tree.selection()
        if not selection:
            self.message_status_label.config(text="⚠️ Please select a channel to update", foreground="orange")
            return
        
        if not self.bot_client or not self.bot_client.is_ready():
            self.message_status_label.config(text="❌ Bot not connected", foreground="red")
            return
        
        tags = self.message_tree.item(selection[0], "tags")
        channel_id = int(tags[0])
        has_message = len(tags) > 1 and tags[1]
        
        if not has_message:
            self.message_status_label.config(
                text=f"⚠️ No message exists for this channel. Use 'Create New' first.", 
                foreground="orange")
            return
        
        async def update():
            success = await self.bot_client.update_single_message(channel_id)
            if success:
                self.root.after(0, lambda: self.message_status_label.config(
                    text=f"✅ Message updated for channel {channel_id}", foreground="green"))
                self.root.after(0, self.update_message_list_display)
            else:
                self.root.after(0, lambda: self.message_status_label.config(
                    text=f"❌ Failed to update message for channel {channel_id}", foreground="red"))
            self.root.after(3000, lambda: self.message_status_label.config(text=""))
        
        asyncio.run_coroutine_threadsafe(update(), self.bot_loop)

    def update_all_messages(self):
        """Update all enabled messages."""
        if not self.bot_client:
            self.message_status_label.config(text="❌ Bot not connected", foreground="red")
            return
        
        async def update():
            await self.bot_client.update_status_messages()
            self.root.after(0, lambda: self.message_status_label.config(
                text="✅ All messages updated", foreground="green"))
            self.root.after(0, self.update_message_list_display)
            self.root.after(3000, lambda: self.message_status_label.config(text=""))
        
        asyncio.run_coroutine_threadsafe(update(), self.bot_loop)

    def create_new_message_dialog(self):
        """Show dialog to create or manually add a message in a selected channel."""
        if not self.bot_client or not self.bot_client.is_ready():
            messagebox.showwarning("Warning", "Bot must be connected to create messages")
            return
        
        selection = self.message_tree.selection()
        selected_channel_id = None
        selected_channel_name = None
        
        if selection:
            tags = self.message_tree.item(selection[0], "tags")
            if tags:
                selected_channel_id = int(tags[0])
                values = self.message_tree.item(selection[0], "values")
                if len(values) >= 3:
                    selected_channel_name = f"{values[1]} → #{values[2]}"
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Add or Create Status Message")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(header_frame, text="Add or Create Status Message", font=('Arial', 14, 'bold')).pack()
        
        if selected_channel_name:
            channel_frame = ttk.Frame(dialog)
            channel_frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(channel_frame, text=f"Selected Channel: ", font=('Arial', 10)).pack(side='left')
            ttk.Label(channel_frame, text=selected_channel_name, font=('Arial', 10, 'bold'), foreground="blue").pack(side='left')
        
        ttk.Separator(dialog, orient='horizontal').pack(fill='x', padx=10, pady=10)
        
        manual_frame = ttk.LabelFrame(dialog, text="📝 Option 1: Add Existing Message ID", padding=10)
        manual_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(manual_frame, text="If you already have a Discord message ID, you can add it here:", 
                  font=("TkDefaultFont", 9)).pack(anchor='w', pady=(0, 10))
        
        id_input_frame = ttk.Frame(manual_frame)
        id_input_frame.pack(fill='x', pady=5)
        
        ttk.Label(id_input_frame, text="Message ID:", font=('Arial', 10)).pack(side='left', padx=(0, 10))
        manual_id_var = tk.StringVar()
        manual_id_entry = ttk.Entry(id_input_frame, textvariable=manual_id_var, width=35)
        manual_id_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Label(manual_frame, text="💡 How to find a message ID: Enable Developer Mode in Discord → Right-click message → Copy ID", 
                  font=("TkDefaultFont", 8), foreground="gray").pack(anchor='w', pady=(5, 5))
        
        manual_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(manual_frame, text="Enable this message immediately", 
                       variable=manual_enabled_var).pack(anchor='w', pady=5)
        
        ttk.Separator(dialog, orient='horizontal').pack(fill='x', padx=10, pady=10)
        
        new_frame = ttk.LabelFrame(dialog, text="✨ Option 2: Create New Message", padding=10)
        new_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        ttk.Label(new_frame, text="Or create a brand new status message:", 
                  font=("TkDefaultFont", 9)).pack(anchor='w', pady=(0, 10))
        
        ttk.Label(new_frame, text="Select Channel:", font=('Arial', 10)).pack(anchor='w', pady=5)
        
        listbox_frame = ttk.Frame(new_frame)
        listbox_frame.pack(fill='both', expand=True, pady=5)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side='right', fill='y')
        
        channel_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, height=6)
        channel_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=channel_listbox.yview)
        
        channel_ids = []
        channel_display_names = []
        for channel_id, settings in self.channel_settings.items():
            if settings.get('enabled', False):
                guild_name = settings.get('guild', 'Unknown')
                channel_name = settings.get('name', 'Unknown')
                display_text = f"{guild_name} → #{channel_name} (ID: {channel_id})"
                channel_listbox.insert(tk.END, display_text)
                channel_ids.append(channel_id)
                channel_display_names.append(display_text)
        
        if selected_channel_id and str(selected_channel_id) in channel_ids:
            idx = channel_ids.index(str(selected_channel_id))
            channel_listbox.selection_set(idx)
            channel_listbox.see(idx)
        
        new_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(new_frame, text="Enable this message immediately", 
                       variable=new_enabled_var).pack(anchor='w', pady=10)
        
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        
        def add_manual_message():
            msg_id = manual_id_var.get().strip()
            if not msg_id:
                messagebox.showwarning("Warning", "Please enter a message ID")
                return
            if not msg_id.isdigit():
                messagebox.showwarning("Warning", "Message ID must be a number")
                return
            
            selection = channel_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a channel from the list")
                return
            
            selected_index = selection[0]
            channel_id = int(channel_ids[selected_index])
            channel_display = channel_display_names[selected_index]
            
            async def add_manual_message_async():
                channel = self.bot_client.get_channel(channel_id)
                if channel:
                    success = self.bot_client.add_or_update_message_id(
                        channel_id, 
                        int(msg_id), 
                        manual_enabled_var.get(),
                        channel.name,
                        channel.guild.name
                    )
                    if success:
                        self.root.after(0, lambda: messagebox.showinfo("Success", 
                            f"✅ Message ID added successfully!\n\nChannel: {channel_display}\nMessage ID: {msg_id}"))
                        self.root.after(0, self.update_message_list_display)
                        self.root.after(0, dialog.destroy)
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", "Failed to add message ID"))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not find channel"))
            
            asyncio.run_coroutine_threadsafe(add_manual_message_async(), self.bot_loop)
        
        def create_new_message():
            selection = channel_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a channel from the list")
                return
            
            selected_index = selection[0]
            channel_id = int(channel_ids[selected_index])
            channel_display = channel_display_names[selected_index]
            
            async def create_message_async():
                msg_id = await self.bot_client.create_new_message(channel_id, new_enabled_var.get())
                if msg_id:
                    self.root.after(0, lambda: messagebox.showinfo("Success", 
                        f"✅ Message created successfully!\n\nChannel: {channel_display}\nMessage ID: {msg_id}"))
                    self.root.after(0, self.update_message_list_display)
                    self.root.after(0, dialog.destroy)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Failed to create message"))
            
            asyncio.run_coroutine_threadsafe(create_message_async(), self.bot_loop)
        
        ttk.Button(button_frame, text="Add Manual ID", command=add_manual_message, width=15).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Create New Message", command=create_new_message, width=15).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=10).pack(side='left', padx=10)
        
        manual_id_entry.focus()

    def remove_selected_message(self):
        """Remove the selected message."""
        selection = self.message_tree.selection()
        if not selection:
            self.message_status_label.config(text="⚠️ Please select a message to remove", foreground="orange")
            return
        
        if messagebox.askyesno("Confirm Remove", "Are you sure you want to remove this message?\nThe bot will no longer update it."):
            tags = self.message_tree.item(selection[0], "tags")
            if tags:
                channel_id = int(tags[0])
                if self.bot_client:
                    self.bot_client.remove_message_id(channel_id)
                    self.update_message_list_display()
                    self.message_status_label.config(text=f"✅ Message removed for channel {channel_id}", foreground="green")
                    self.root.after(3000, lambda: self.message_status_label.config(text=""))

    def enable_all_messages(self):
        """Enable all messages."""
        if self.bot_client and hasattr(self.bot_client, 'message_ids'):
            for channel_id in list(self.bot_client.message_ids.keys()):
                if not self.bot_client.message_ids[channel_id].get("enabled", True):
                    self.bot_client.toggle_message_enabled(channel_id)
            self.update_message_list_display()
            self.message_status_label.config(text="✅ All messages enabled", foreground="green")
            self.root.after(3000, lambda: self.message_status_label.config(text=""))

    def disable_all_messages(self):
        """Disable all messages."""
        if self.bot_client and hasattr(self.bot_client, 'message_ids'):
            for channel_id in list(self.bot_client.message_ids.keys()):
                if self.bot_client.message_ids[channel_id].get("enabled", True):
                    self.bot_client.toggle_message_enabled(channel_id)
            self.update_message_list_display()
            self.message_status_label.config(text="⚠️ All messages disabled", foreground="orange")
            self.root.after(3000, lambda: self.message_status_label.config(text=""))

    # ================================================================
    # Manual control handlers
    # ================================================================

    def on_mode_change(self):
        mode = "MANUAL" if self.manual_control_mode.get() else "AUTO"
        self.mode_status_label.config(
            text=(
                f"⚠️ Current Mode: {mode} - "
                + ("Bot will NEVER auto-create messages"
                   if self.manual_control_mode.get()
                   else "Bot may auto-create messages if needed")
            ),
            foreground="red" if self.manual_control_mode.get() else "green",
        )
        if self.bot_client:
            self.bot_client.manual_mode = self.manual_control_mode.get()
        self.log_to_console(f"Switched to {mode} mode")
        self.save_config()

    def load_current_message_id_display(self):
        """Legacy method - kept for compatibility"""
        pass

    # ================================================================
    # Channel management handlers
    # ================================================================

    def on_tree_click(self, event):
        region = self.channel_tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.channel_tree.identify_column(event.x)
            if column == "#1":
                item = self.channel_tree.identify_row(event.y)
                if item:
                    channel_id = self.channel_tree.item(item, "tags")[0]
                    if channel_id in self.channel_settings:
                        self.channel_settings[channel_id]['enabled'] = \
                            not self.channel_settings[channel_id]['enabled']
                        self.update_channel_tree()
                        if self.bot_client:
                            self.bot_client.channel_settings = self.channel_settings
                        self.log_to_console(
                            f"Channel {'enabled' if self.channel_settings[channel_id]['enabled'] else 'disabled'}: {channel_id}"
                        )
                        self.save_config()

    def add_channel(self):
        channel_id = self.channel_var.get().strip()
        if not channel_id:
            messagebox.showerror("Error", "Please enter a channel ID")
            return
        if not channel_id.isdigit():
            messagebox.showerror("Error", "Channel ID must be numeric")
            return
        if channel_id in self.channel_settings:
            messagebox.showwarning("Warning", "Channel already in the list")
            return

        self.channel_settings[channel_id] = {
            "enabled": True,
            "name": "Unknown (run bot to update)",
            "guild": "Unknown",
        }
        self.update_channel_tree()
        self.channel_var.set("")
        self.log_to_console(f"Added channel ID: {channel_id}")

        if self.bot_client and self.bot_client.is_ready():
            self.bot_client.channel_settings = self.channel_settings
            asyncio.run_coroutine_threadsafe(
                self.bot_client.update_channel_info(), self.bot_loop)
        else:
            self.log_to_console("Channel info will update when bot is started")
        self.save_config()

    def remove_channel(self):
        selected = self.channel_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a channel to remove")
            return
        channel_id = self.channel_tree.item(selected[0], "tags")[0]
        if channel_id in self.channel_settings:
            del self.channel_settings[channel_id]
            self.update_channel_tree()
            self.log_to_console(f"Removed channel ID: {channel_id}")
            if self.bot_client:
                self.bot_client.channel_settings = self.channel_settings
            self.save_config()

    def enable_all_channels(self):
        for cid in self.channel_settings:
            self.channel_settings[cid]['enabled'] = True
        self.update_channel_tree()
        if self.bot_client:
            self.bot_client.channel_settings = self.channel_settings
        self.log_to_console("All channels enabled")
        self.save_config()

    def disable_all_channels(self):
        for cid in self.channel_settings:
            self.channel_settings[cid]['enabled'] = False
        self.update_channel_tree()
        if self.bot_client:
            self.bot_client.channel_settings = self.channel_settings
        self.log_to_console("All channels disabled")
        self.save_config()

    def refresh_channel_info(self):
        if not self.bot_client or not self.bot_client.is_ready():
            messagebox.showwarning(
                "Warning",
                "Bot must be running to refresh channel info.\nStart the bot first, then try again.",
            )
            return
        self.log_to_console("🔄 Refreshing channel information from Discord...")
        asyncio.run_coroutine_threadsafe(
            self.bot_client.update_channel_info(), self.bot_loop)

    def update_channel_tree(self):
        for item in self.channel_tree.get_children():
            self.channel_tree.delete(item)

        if not self.channel_settings:
            self.channel_tree.insert("", tk.END,
                                     values=("", "No channels configured",
                                             "Add a channel ID above", ""))
        else:
            for channel_id, settings in self.channel_settings.items():
                enabled = settings.get('enabled', False)
                status = "✅" if enabled else "❌"
                self.channel_tree.insert(
                    "", tk.END,
                    values=(status,
                            settings.get('guild', 'Unknown'),
                            settings.get('name', 'Unknown'),
                            channel_id),
                    tags=(channel_id,),
                )

    # ================================================================
    # Console management
    # ================================================================

    def log_to_console(self, message):
        """Log message to console if logging is enabled."""
        if not self.logging_enabled_var.get():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
            return
        
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        print(formatted, end='')
        try:
            if hasattr(self, 'console_text') and self.console_text:
                self.console_text.insert(tk.END, formatted)
                self.console_text.see(tk.END)
                self.root.update_idletasks()
        except Exception as e:
            print(f"GUI console error: {e}")

    def clear_console(self):
        if messagebox.askyesno("Confirm", "Save a backup before clearing?"):
            self.save_manual_backup()
        self.console_text.delete(1.0, tk.END)
        self.log_to_console("=== Console Cleared ===")

    def schedule_console_cleanup(self):
        self.auto_clear_console()
        self.cleanup_old_backups()
        self.root.after(3600000, self.schedule_console_cleanup)

    def auto_clear_console(self):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"auto_console_backup_{timestamp}.txt"
            backup_path = os.path.join(CONSOLE_BACKUP_DIR, backup_filename)

            console_content = self.console_text.get(1.0, tk.END)
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(console_content)

            self.console_text.delete(1.0, tk.END)

            backup_count = len([
                fn for fn in os.listdir(CONSOLE_BACKUP_DIR)
                if fn.startswith("auto_console_backup_")
            ])
            self.log_to_console(f"🧹 Console auto-cleared (backup saved: {backup_filename})")
            self.log_to_console(
                f"📊 Total backups: {backup_count} (keeping last {CONSOLE_BACKUP_HOURS} hours)"
            )
        except Exception as e:
            self.log_to_console(f"Error auto-clearing console: {e}")

    def save_manual_backup(self):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"manual_console_backup_{timestamp}.txt"
            backup_path = os.path.join(CONSOLE_BACKUP_DIR, backup_filename)
            console_content = self.console_text.get(1.0, tk.END)
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(console_content)
            self.log_to_console(f"💾 Manual backup saved: {backup_filename}")
            messagebox.showinfo("Success", f"Backup saved:\n{backup_filename}")
        except Exception as e:
            self.log_to_console(f"Error saving manual backup: {e}")
            messagebox.showerror("Error", f"Failed to save backup: {e}")

    def cleanup_old_backups(self):
        try:
            if not os.path.exists(CONSOLE_BACKUP_DIR):
                return
            now = datetime.datetime.now()
            cutoff_time = now - datetime.timedelta(hours=CONSOLE_BACKUP_HOURS)
            deleted_count = 0
            for filename in os.listdir(CONSOLE_BACKUP_DIR):
                if filename.endswith(".txt") and (
                    "auto_console_backup_" in filename
                    or "manual_console_backup_" in filename
                ):
                    filepath = os.path.join(CONSOLE_BACKUP_DIR, filename)
                    file_modified = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_modified < cutoff_time:
                        os.remove(filepath)
                        deleted_count += 1
            if deleted_count > 0:
                self.log_to_console(
                    f"🧹 Deleted {deleted_count} old console backup(s) "
                    f"(older than {CONSOLE_BACKUP_HOURS} hours)"
                )
            else:
                self.log_to_console("No old backups to clean up")
        except Exception as e:
            self.log_to_console(f"Error cleaning up old backups: {e}")

    def list_backups(self):
        try:
            if not os.path.exists(CONSOLE_BACKUP_DIR):
                self.log_to_console("No backup directory found")
                return
            backups = []
            for filename in os.listdir(CONSOLE_BACKUP_DIR):
                if filename.endswith(".txt") and (
                    "auto_console_backup_" in filename
                    or "manual_console_backup_" in filename
                ):
                    filepath = os.path.join(CONSOLE_BACKUP_DIR, filename)
                    file_modified = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                    file_size = os.path.getsize(filepath)
                    backups.append((filename, file_modified, file_size))
            backups.sort(key=lambda x: x[1], reverse=True)
            self.log_to_console(f"📋 Current backups ({len(backups)} total):")
            for filename, modified, size in backups[:10]:
                age = datetime.datetime.now() - modified
                hours = int(age.total_seconds() / 3600)
                self.log_to_console(f"  • {filename} ({hours}h old, {size} bytes)")
            if len(backups) > 10:
                self.log_to_console(f"  ... and {len(backups) - 10} more")
        except Exception as e:
            self.log_to_console(f"Error listing backups: {e}")

    # ================================================================
    # Guild / server tab helpers
    # ================================================================

    def update_guild_list(self, guilds):
        for item in self.server_tree.get_children():
            self.server_tree.delete(item)
        for guild in guilds:
            owner_name = str(guild.owner) if guild.owner else "Unknown"
            self.server_tree.insert('', 'end', values=(
                guild.name, str(guild.id), owner_name, guild.member_count,
            ), tags=(guild.id,))

    def refresh_guild_list(self):
        if self.bot_client and self.bot_client.is_ready():
            self.update_guild_list(self.bot_client.guilds)

    def generate_invite(self):
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server first")
            return
        guild_id = self.server_tree.item(selection[0])['tags'][0]
        guild = self.bot_client.get_guild(int(guild_id))
        if guild:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    async def create_invite():
                        try:
                            invite = await channel.create_invite(max_age=86400, max_uses=1)
                            self.root.after(0, lambda: self.show_invite_dialog(str(invite)))
                        except Exception as e:
                            self.root.after(0, lambda: messagebox.showerror(
                                "Error", f"Failed to create invite: {e}"))
                    asyncio.run_coroutine_threadsafe(create_invite(), self.bot_loop)
                    break

    def show_invite_dialog(self, invite_url):
        dialog = tk.Toplevel(self.root)
        dialog.title("Invite Link")
        dialog.geometry("400x100")
        ttk.Label(dialog, text="Invite Link (expires in 24 hours):").pack(pady=5)
        url_entry = ttk.Entry(dialog, width=50)
        url_entry.insert(0, invite_url)
        url_entry.pack(pady=5)
        url_entry.config(state='readonly')
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=5)

    def leave_server(self):
        selection = self.server_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a server first")
            return
        if messagebox.askyesno("Confirm", "Are you sure you want to leave this server?"):
            guild_id = self.server_tree.item(selection[0])['tags'][0]
            guild = self.bot_client.get_guild(int(guild_id))
            if guild:
                async def leave():
                    try:
                        await guild.leave()
                        self.root.after(0, self.refresh_guild_list)
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Error", f"Failed to leave server: {e}"))
                asyncio.run_coroutine_threadsafe(leave(), self.bot_loop)

    # ================================================================
    # File / config helpers
    # ================================================================

    def browse_server_file(self):
        filename = filedialog.askopenfilename(
            title="Select Server File",
            filetypes=[("Batch files", "*.bat"), ("PowerShell files", "*.ps1"),
                       ("All files", "*.*")],
        )
        if filename:
            self.server_file_path.set(filename)
            self.log_to_console(f"Selected server file: {filename}")
            self.save_config()

    def save_game_id(self):
        """Save Game ID to config file."""
        self.save_config()
        self.log_to_console(f"Game ID saved: {self.game_id_var.get()}")

    def save_current_game(self):
        """Save current game to config file."""
        self.save_config()
        self.log_to_console(f"Current game saved: {self.current_game_var.get()}")

    def load_current_game(self):
        """Load current game from config - handled in load_config"""
        pass

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                
                encrypted_token = config.get('token', '')
                if encrypted_token and self.encryption_manager.is_key_available():
                    decrypted_token = self.encryption_manager.decrypt(encrypted_token)
                    self.token_var.set(decrypted_token)
                else:
                    self.token_var.set('')
                
                self.save_token_var.set(config.get('save_token', False))
                self.auto_connect_var.set(config.get('auto_connect', False))
                self.auto_start_server_var.set(config.get('auto_start_server', False))
                self.auto_restart_server_var.set(config.get('auto_restart_server', True))
                self.server_file_path.set(config.get('server_file', ''))
                self.process_name_var.set(config.get('process_name', 'CoreKeeperServer.exe'))
                self.update_interval_var.set(config.get('update_interval', 5))
                self.manual_control_mode.set(config.get('manual_mode', False))
                
                self.current_game_var.set(config.get('current_game', ''))
                self.game_id_var.set(config.get('game_id', ''))

                loaded_channels = config.get('channel_settings', {})
                self.channel_settings = {
                    cid: {
                        "enabled": cdata.get('enabled', True),
                        "name": cdata.get('name', 'Unknown'),
                        "guild": cdata.get('guild', 'Unknown'),
                    }
                    for cid, cdata in loaded_channels.items()
                }

                self.log_to_console(
                    f"Loaded config: auto_connect={self.auto_connect_var.get()}, "
                    f"auto_start={self.auto_start_server_var.get()}"
                )

                if hasattr(self, 'channel_tree') and self.channel_tree:
                    self.root.after(100, self.update_channel_tree)

                self.on_mode_change()

            except Exception as e:
                self.log_to_console(f"Error loading config: {e}")

    def save_config(self):
        token_to_save = ""
        if self.save_token_var.get():
            token_value = self.token_var.get()
            if token_value and self.encryption_manager.is_key_available():
                token_to_save = self.encryption_manager.encrypt(token_value)
        
        config = {
            'token': token_to_save,
            'save_token': self.save_token_var.get(),
            'auto_connect': self.auto_connect_var.get(),
            'auto_start_server': self.auto_start_server_var.get(),
            'auto_restart_server': self.auto_restart_server_var.get(),
            'server_file': self.server_file_path.get(),
            'process_name': self.process_name_var.get(),
            'update_interval': self.update_interval_var.get(),
            'manual_mode': self.manual_control_mode.get(),
            'current_game': self.current_game_var.get(),
            'game_id': self.game_id_var.get(),
            'channel_settings': self.channel_settings,
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            
            if self.save_token_var.get():
                self.log_to_console("Configuration saved successfully (token encrypted)")
            else:
                self.log_to_console("Configuration saved successfully")
            
        except Exception as e:
            self.log_to_console(f"Error saving configuration: {e}")
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
            
    def verify_encryption_integrity(self):
        if self.encryption_manager.verify_key_integrity():
            self.log_to_console("✅ Encryption key integrity verified - all key files present")
            messagebox.showinfo("Security Check", 
                               "Encryption keys are intact and verified.\n"
                               "Files present:\n"
                               f"• {KEY_FILE}\n"
                               f"• {KEY_BACKUP_FILE}\n"
                               f"• {KEY_METADATA_FILE}")
        else:
            self.log_to_console("⚠️ Encryption key integrity check failed - some files missing")
            messagebox.showwarning("Security Warning", 
                                  "Some encryption key files are missing!\n"
                                  "Your saved tokens may not be recoverable.")

    # ================================================================
    # Logging management
    # ================================================================
    
    def load_logging_config(self):
        if os.path.exists(LOGGING_CONFIG_FILE):
            try:
                with open(LOGGING_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.logging_enabled_var.set(config.get('logging_enabled', True))
                    print(f"Loaded logging config: enabled={self.logging_enabled_var.get()}")
            except Exception as e:
                print(f"Error loading logging config: {e}")
                self.logging_enabled_var.set(True)
        else:
            self.logging_enabled_var.set(True)

    def save_logging_config(self):
        config = {
            'logging_enabled': self.logging_enabled_var.get()
        }
        try:
            with open(LOGGING_CONFIG_FILE, 'w') as f:
                json.dump(config, f)
            print(f"Logging config saved: enabled={self.logging_enabled_var.get()}")
        except Exception as e:
            print(f"Error saving logging config: {e}")

    def update_logging_ui(self):
        """Update the logging toggle button and status label based on current setting."""
        if hasattr(self, 'logging_toggle_button') and self.logging_toggle_button:
            if self.logging_enabled_var.get():
                self.logging_toggle_button.config(text="Disable Logging")
                self.logging_status_label.config(text="Status: Enabled ✓", foreground="green")
            else:
                self.logging_toggle_button.config(text="Enable Logging")
                self.logging_status_label.config(text="Status: Disabled ✗", foreground="red")

    def toggle_logging(self):
        current_value = self.logging_enabled_var.get()
        self.logging_enabled_var.set(not current_value)
        self.save_logging_config()
        self.update_logging_ui()
        
        if self.logging_enabled_var.get():
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] ✅ Logging enabled\n"
            print(formatted, end='')
            try:
                if hasattr(self, 'console_text') and self.console_text:
                    self.console_text.insert(tk.END, formatted)
                    self.console_text.see(tk.END)
                    self.root.update_idletasks()
            except Exception:
                pass

    # ================================================================
    # Bot lifecycle
    # ================================================================

    def apply_update_interval(self):
        interval_minutes = self.update_interval_var.get()
        if interval_minutes < 1:
            interval_minutes = 1
            self.update_interval_var.set(1)
        if self.bot_client and self.bot_client.is_ready():
            self.bot_client.check_message_task.change_interval(seconds=interval_minutes * 60)
            self.log_to_console(f"Status update interval changed to {interval_minutes} minutes")
            # Force an immediate update to show the new interval
            self.force_status_update()
        else:
            self.log_to_console(
                f"Update interval set to {interval_minutes} minutes "
                f"(will apply when bot connects)"
            )
        self.save_config()

    def force_status_update(self):
        if self.bot_client and self.bot_client.is_ready():
            asyncio.run_coroutine_threadsafe(
                self.bot_client.force_status_update(), self.bot_loop)
            self.log_to_console("Forced immediate status update")

    def connect_bot(self):
        if not self.token_var.get():
            messagebox.showwarning("No Token", "Please enter a bot token")
            return

        import threading
        self.log_to_console("Attempting to connect bot...")
        self.bot_thread = threading.Thread(
            target=self.run_bot, args=(self.token_var.get(),), daemon=True)
        self.bot_thread.start()

        if self.auto_start_server_var.get() and self.server_file_path.get():
            self.log_to_console("Auto-start server is enabled - will start in 10 seconds...")
            self.root.after(10000, self.start_server)

    def run_bot(self, token):
        import asyncio
        from bot_client import DiscordBotClient

        self.bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.bot_loop)
        self.bot_client = DiscordBotClient(self, channel_settings=self.channel_settings)
        try:
            self.bot_loop.run_until_complete(self.bot_client.start(token))
        except Exception as e:
            self.root.after(0, lambda: self.log_to_console(f"Bot error: {e}"))
            self.root.after(0, lambda: self.update_status("Disconnected", False))
        finally:
            self.bot_loop.close()

    def disconnect_bot(self):
        if self.bot_client:
            async def disconnect():
                await self.bot_client.close()
            if self.bot_loop:
                asyncio.run_coroutine_threadsafe(disconnect(), self.bot_loop)
            self.update_status("Disconnected", False)
            self.log_to_console("Bot disconnected")