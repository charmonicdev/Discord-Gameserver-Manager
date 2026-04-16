# server_manager.py
# Handles starting, stopping, monitoring, and restarting the game server process.

import os
import subprocess
import threading
import time
import psutil
import tkinter as tk
from tkinter import ttk, messagebox


class ServerManager:
    """
    Mixin that provides all game-server process management logic to BotGUI.

    Expects the following attributes to already exist on `self`:
        process_name_var, server_file_path, auto_restart_server_var,
        launcher_pid_label, server_pid_label, server_status_label,
        start_server_button, kill_server_button,
        root, log_to_console, force_status_update
    """

    def __init__(self):
        # These will be set by BotGUI
        self.process_name_var = None
        self.server_file_path = None
        self.auto_restart_server_var = None
        self.launcher_pid_label = None
        self.server_pid_label = None
        self.server_status_label = None
        self.start_server_button = None
        self.kill_server_button = None
        self.root = None
        self.server_monitor_running = False
        self.server_monitor_thread = None
        self.server_process = None
        self.launcher_process = None
        self.last_server_status = None
        self.restart_attempts = 0
        self.max_restart_attempts = 3
        self.is_killing = False
        self.startup_grace_period = 30
        self.startup_time = 0

    # ------------------------------------------------------------------
    # Process discovery
    # ------------------------------------------------------------------

    def scan_for_process(self):
        """Scan for processes matching the configured name."""
        process_name = self.process_name_var.get().lower()
        if not process_name:
            messagebox.showwarning("Warning", "Please enter a process name to scan for")
            return

        found_pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if process_name in proc.info['name'].lower():
                    found_pids.append(proc.info['pid'])
            except Exception:
                continue

        if found_pids:
            self.log_to_console(
                f"Found {len(found_pids)} process(es) matching '{process_name}': {found_pids}"
            )
            if len(found_pids) == 1:
                self.server_pid_label.config(text=str(found_pids[0]), foreground="green")
                messagebox.showinfo("Process Found", f"Found process with PID: {found_pids[0]}")
            else:
                self.server_pid_label.config(text="Multiple found", foreground="orange")
                messagebox.showinfo("Multiple Processes", f"Found multiple processes:\n{found_pids}")
        else:
            self.server_pid_label.config(text="Not found", foreground="red")
            self.log_to_console(f"No processes found matching '{process_name}'")

    def check_existing_server(self):
        """Check if a server process is already running."""
        process_name = self.process_name_var.get().lower()
        if not process_name:
            return None
        
        found_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if process_name in proc.info['name'].lower():
                    found_processes.append(proc)
            except Exception:
                continue
        
        return found_processes

    def is_server_running(self):
        """Check if the monitored server process is running."""
        if self.server_process:
            try:
                if isinstance(self.server_process, psutil.Process):
                    return self.server_process.is_running()
                else:
                    return self.server_process.poll() is None
            except Exception:
                return False
        return False

    def find_server_process(self):
        """Find the server process by the configured name."""
        process_name = self.process_name_var.get().lower()
        if not process_name:
            return None

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if process_name in proc.info['name'].lower():
                    self.log_to_console(
                        f"✅ Found {proc.info['name']} with PID: {proc.info['pid']}"
                    )
                    return psutil.Process(proc.info['pid'])
            except Exception:
                continue
        return None

    def update_server_status_display(self, status, color=None):
        """Update the server status label and indicator."""
        status_map = {
            "stopped": {"text": "⚫ Stopped", "color": "gray"},
            "starting": {"text": "🟡 Starting...", "color": "orange"},
            "running": {"text": "🟢 Running", "color": "green"},
            "stopping": {"text": "🟠 Stopping...", "color": "orange"},
            "restarting": {"text": "🔵 Restarting...", "color": "blue"},
            "crashed": {"text": "🔴 Crashed", "color": "red"},
            "waiting": {"text": "⏳ Waiting...", "color": "gray"},
        }
        
        info = status_map.get(status, {"text": status, "color": color or "gray"})
        display_text = info["text"]
        display_color = info["color"] if not color else color
        
        def update():
            try:
                if hasattr(self, 'server_status_label') and self.server_status_label:
                    self.server_status_label.config(text=display_text, foreground=display_color)
            except Exception as e:
                self.log_to_console(f"Error updating status display: {e}")
        
        self.root.after(0, update)

    def show_auto_close_dialog(self, title, message, default_yes=True, timeout=15):
        """
        Show a dialog that automatically closes after timeout and returns default.
        Returns True if Yes/OK, False if No/Cancel.
        """
        result = {"value": default_yes}
        dialog = None
        remaining = {"timeout": timeout}
        
        def on_yes():
            result["value"] = True
            if dialog:
                dialog.destroy()
        
        def on_no():
            result["value"] = False
            if dialog:
                dialog.destroy()
        
        def update_timer():
            if remaining["timeout"] > 0:
                if dialog and dialog.winfo_exists():
                    remaining["timeout"] -= 1
                    timer_label.config(text=f"Auto-selecting 'Yes' in {remaining['timeout']} seconds...")
                    dialog.after(1000, update_timer)
            else:
                if dialog and dialog.winfo_exists():
                    on_yes()
        
        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Create main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill='both', expand=True)
        
        # Warning icon
        icon_label = ttk.Label(main_frame, text="⚠️", font=('Arial', 32))
        icon_label.pack(pady=(0, 10))
        
        # Message label
        msg_label = ttk.Label(main_frame, text=message, wraplength=450, justify='left')
        msg_label.pack(pady=(0, 15), fill='x')
        
        # Timer label
        timer_label = ttk.Label(main_frame, text=f"Auto-selecting 'Yes' in {timeout} seconds...", 
                                font=('Arial', 9), foreground="gray")
        timer_label.pack(pady=(0, 15))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0))
        
        yes_btn = ttk.Button(button_frame, text="Yes - Kill & Restart", command=on_yes, width=20)
        yes_btn.pack(side='left', padx=10)
        
        no_btn = ttk.Button(button_frame, text="No - Attach to Existing", command=on_no, width=20)
        no_btn.pack(side='left', padx=10)
        
        # Force geometry update to calculate proper size
        dialog.update_idletasks()
        
        # Get the requested size
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        
        # Set minimum size and center
        dialog.minsize(width, height)
        
        # Center the dialog
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")
        
        # Start timer
        dialog.after(1000, update_timer)
        
        # Wait for dialog to close
        self.root.wait_window(dialog)
        
        return result["value"]

    # ------------------------------------------------------------------
    # Process termination
    # ------------------------------------------------------------------

    def kill_process_tree(self, proc, timeout=60):
        """Kill a process and all its children with timeout."""
        if not proc:
            return False

        killed_any = False
        try:
            if isinstance(proc, psutil.Process):
                pid = proc.pid
                proc_name = proc.name()
                children = proc.children(recursive=True)
            elif isinstance(proc, subprocess.Popen):
                pid = proc.pid
                proc_name = "Launcher"
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                except Exception:
                    children = []
            else:
                return False

            self.log_to_console(f"Killing process tree for {proc_name} (PID: {pid})...")

            for child in children:
                try:
                    child.kill()
                    self.log_to_console(f"  Killed child PID: {child.pid}")
                    killed_any = True
                except Exception:
                    pass

            try:
                proc.kill()
                self.log_to_console(f"  Killed main process PID: {pid}")
                killed_any = True
            except Exception:
                pass

            start_time = time.time()
            while time.time() - start_time < timeout:
                all_dead = True

                try:
                    if isinstance(proc, psutil.Process):
                        if proc.is_running():
                            all_dead = False
                    else:
                        if proc.poll() is None:
                            all_dead = False
                except Exception:
                    pass

                for child in children:
                    try:
                        if child.is_running():
                            all_dead = False
                            break
                    except Exception:
                        pass

                if all_dead:
                    self.log_to_console("✅ All processes terminated successfully")
                    return True

                time.sleep(1)

            self.log_to_console("⚠️ Timeout reached, forcing termination...")
            try:
                proc.kill()
            except Exception:
                pass

            return killed_any

        except Exception as e:
            self.log_to_console(f"Error killing process: {e}")
            return False

    # ------------------------------------------------------------------
    # Start / kill / restart
    # ------------------------------------------------------------------

    def start_server(self, force=False):
        """Start the server, with option to force kill existing instances."""
        if not self.server_file_path.get():
            messagebox.showwarning("No File", "Please select a server file first")
            return

        # Check for existing server processes
        existing_processes = self.check_existing_server()
        
        if existing_processes and not force:
            # Show auto-close dialog
            message = (
                f"Found {len(existing_processes)} existing server process(es).\n\n"
                "What would you like to do?\n\n"
                "• Yes: Kill existing process(es) and start a new instance\n"
                "• No: Attach to the existing server process"
            )
            
            result = self.show_auto_close_dialog(
                title="Server Already Running",
                message=message,
                default_yes=True,
                timeout=15
            )
            
            if result:
                self.log_to_console("User chose to kill existing processes and restart")
                self.log_to_console("Killing existing server processes...")
                self.update_server_status_display("stopping")
                for proc in existing_processes:
                    try:
                        self.kill_process_tree(proc)
                        self.log_to_console(f"Killed process PID: {proc.pid}")
                    except Exception as e:
                        self.log_to_console(f"Error killing process {proc.pid}: {e}")
                time.sleep(2)
                # Continue to start new server
            else:
                # Attach to existing server
                self.log_to_console("User chose to attach to existing server")
                self.log_to_console("Attaching to existing server process...")
                self.server_process = existing_processes[0]
                self.launcher_process = None
                self.start_server_button.config(state='disabled')
                self.kill_server_button.config(state='normal')
                self.update_server_status_display("running")
                self.server_pid_label.config(text=str(self.server_process.pid), foreground="green")
                self.launcher_pid_label.config(text="Attached", foreground="blue")
                
                # Start monitoring
                self.server_monitor_running = True
                self.server_monitor_thread = threading.Thread(
                    target=self.monitor_server, daemon=True
                )
                self.server_monitor_thread.start()
                
                # FORCE MULTIPLE STATUS UPDATES WHEN ATTACHING
                self.log_to_console("🔄 Forcing Discord status update...")
                
                # Use a helper function to ensure status updates happen
                def force_updates():
                    try:
                        self.log_to_console("Attempting to force status update...")
                        self.force_status_update()
                        self.log_to_console("Status update called")
                    except Exception as e:
                        self.log_to_console(f"Error forcing status update: {e}")
                
                # Call immediately
                force_updates()
                
                # Schedule multiple updates with delays
                self.root.after(2000, force_updates)
                self.root.after(5000, force_updates)
                self.root.after(10000, force_updates)
                
                return
        
        # Start new server
        self.update_server_status_display("starting")
        self.log_to_console("🚀 Starting server...")

        try:
            file_path = self.server_file_path.get()
            working_dir = os.path.dirname(file_path)

            self.log_to_console(f"Starting server launcher from: {file_path}")

            if file_path.endswith('.ps1'):
                self.launcher_process = subprocess.Popen(
                    ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-File', file_path],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                self.launcher_process = subprocess.Popen(
                    file_path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=working_dir
                )

            launcher_pid = self.launcher_process.pid
            self.launcher_pid_label.config(text=str(launcher_pid), foreground="green")
            self.log_to_console(f"Launcher started with PID: {launcher_pid}")

            self.startup_time = time.time()

            def find_server():
                max_attempts = 60
                attempt = 0
                found_process = None

                self.log_to_console("Scanning for server process...")
                while attempt < max_attempts and not found_process:
                    found_process = self.find_server_process()
                    if found_process:
                        self.server_process = found_process
                        self.root.after(0, lambda: self.server_pid_label.config(
                            text=str(found_process.pid), foreground="green"))
                        self.root.after(0, lambda: self.update_server_status_display("running"))
                        self.root.after(0, self.force_status_update)
                        self.log_to_console(f"✅ Found server process PID: {found_process.pid}")
                        break
                    attempt += 1
                    if attempt % 10 == 0:
                        self.log_to_console(
                            f"Still scanning for server process... ({attempt}/{max_attempts})"
                        )
                    time.sleep(1)

                if not found_process:
                    self.root.after(0, lambda: self.server_pid_label.config(
                        text="Not found", foreground="orange"))
                    self.root.after(0, lambda: self.update_server_status_display("stopped"))
                    self.log_to_console("⚠️ Could not find server process - check process name")

            scanner_thread = threading.Thread(target=find_server, daemon=True)
            scanner_thread.start()

            self.start_server_button.config(state='disabled')
            self.kill_server_button.config(state='normal')
            self.restart_attempts = 0
            self.is_killing = False

            self.server_monitor_running = True
            self.server_monitor_thread = threading.Thread(
                target=self.monitor_server, daemon=True
            )
            self.server_monitor_thread.start()

            self.force_status_update()

        except Exception as e:
            error_msg = f"Failed to start server: {e}"
            self.log_to_console(f"❌ {error_msg}")
            self.update_server_status_display("stopped")
            messagebox.showerror("Error", error_msg)
            import traceback
            traceback.print_exc()

    def kill_server(self):
        """Kill the server and all related processes."""
        if self.is_killing:
            self.log_to_console("Kill already in progress, ignoring...")
            return

        self.is_killing = True
        self.update_server_status_display("stopping")
        self.log_to_console("🛑 Kill server command received...")

        def kill_processes():
            try:
                if self.server_process:
                    self.log_to_console("Killing server process...")
                    self.kill_process_tree(self.server_process)
                    self.server_process = None

                time.sleep(2)

                if self.launcher_process:
                    self.log_to_console("Killing launcher process...")
                    self.kill_process_tree(self.launcher_process)
                    self.launcher_process = None

                self.log_to_console("Waiting 5 seconds for processes to fully terminate...")
                time.sleep(5)

                process_name = self.process_name_var.get().lower()
                if process_name:
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if process_name in proc.info['name'].lower():
                                self.log_to_console(
                                    f"Found lingering {proc.info['name']} "
                                    f"(PID: {proc.info['pid']}) - killing..."
                                )
                                self.kill_process_tree(psutil.Process(proc.info['pid']))
                        except Exception:
                            continue

                self.root.after(0, self.update_after_kill)

            except Exception as e:
                self.log_to_console(f"Error during kill: {e}")
                self.root.after(0, self.update_after_kill)

        kill_thread = threading.Thread(target=kill_processes, daemon=True)
        kill_thread.start()

    def update_after_kill(self):
        """Update GUI after kill process completes."""
        self.launcher_pid_label.config(text="Not running", foreground="gray")
        self.server_pid_label.config(text="Not found", foreground="gray")
        self.start_server_button.config(state='normal')
        self.kill_server_button.config(state='disabled')
        self.server_monitor_running = False
        self.is_killing = False
        self.startup_time = 0
        self.update_server_status_display("stopped")

        self.log_to_console("✅ Kill process completed - all server processes terminated")
        self.force_status_update()

    def restart_server(self):
        """Restart the server in a non-blocking way."""
        self.log_to_console("🔄 Restarting server...")
        self.update_server_status_display("restarting")
        
        # Force a status update to show server is down
        self.force_status_update()

        def restart_thread():
            # Kill existing processes
            if self.server_process:
                self.kill_process_tree(self.server_process)
                self.server_process = None

            if self.launcher_process:
                self.kill_process_tree(self.launcher_process)
                self.launcher_process = None

            # Update GUI to show waiting state
            self.root.after(0, lambda: self.launcher_pid_label.config(text="Restarting...", foreground="orange"))
            self.root.after(0, lambda: self.server_pid_label.config(text="Restarting...", foreground="orange"))
            
            self.log_to_console("Waiting 5 seconds before restart...")
            
            # Use a loop with small sleeps to keep GUI responsive
            for i in range(5):
                time.sleep(1)
                self.log_to_console(f"Restarting in {5-i} seconds...")
            
            # Update GUI before starting
            self.root.after(0, lambda: self.launcher_pid_label.config(text="Starting...", foreground="orange"))
            self.root.after(0, lambda: self.server_pid_label.config(text="Starting...", foreground="orange"))
            self.root.after(0, lambda: self.update_server_status_display("starting"))
            
            # Start the server
            self.start_server(force=True)
            
            # After server starts, force another status update
            time.sleep(3)  # Give server time to initialize
            self.root.after(0, self.force_status_update)
        
        restart_thread_obj = threading.Thread(target=restart_thread, daemon=True)
        restart_thread_obj.start()

    def handle_server_crash(self):
        """Handle server crash without auto-restart."""
        self.log_to_console("❌ Server crashed and will not auto-restart")
        self.server_process = None
        self.launcher_process = None
        self.start_server_button.config(state='normal')
        self.kill_server_button.config(state='disabled')
        self.server_monitor_running = False
        self.startup_time = 0

        self.launcher_pid_label.config(text="Not running", foreground="gray")
        self.server_pid_label.config(text="Crashed", foreground="red")
        self.update_server_status_display("crashed")

        self.force_status_update()

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    def monitor_server(self):
        """Monitor server process status and handle crashes/restarts."""
        self.log_to_console("Server monitor thread started")

        while self.server_monitor_running:
            try:
                if self.is_killing:
                    time.sleep(2)
                    continue

                if self.startup_time > 0:
                    time_since_startup = time.time() - self.startup_time
                    if time_since_startup < self.startup_grace_period:
                        time.sleep(5)
                        continue

                server_running = False

                if self.server_process:
                    try:
                        if isinstance(self.server_process, psutil.Process):
                            server_running = self.server_process.is_running()
                        else:
                            server_running = self.server_process.poll() is None
                    except Exception:
                        server_running = False

                launcher_running = False
                if self.launcher_process:
                    try:
                        launcher_running = self.launcher_process.poll() is None
                    except Exception:
                        launcher_running = False

                if not server_running and launcher_running and not self.is_killing:
                    self.log_to_console("⚠️ Server process died, killing launcher...")
                    self.kill_process_tree(self.launcher_process)
                    self.launcher_process = None

                # Update status display based on server state
                if server_running and not self.is_killing and self.startup_time > 0:
                    self.root.after(0, lambda: self.update_server_status_display("running"))

                if (
                    self.last_server_status is not None
                    and self.last_server_status
                    and not server_running
                    and not self.is_killing
                    and self.startup_time > 0
                    and time.time() - self.startup_time > self.startup_grace_period
                ):
                    self.log_to_console("💥 Server crashed!")
                    self.root.after(0, lambda: self.server_pid_label.config(
                        text="Crashed", foreground="red"))

                    if (
                        self.auto_restart_server_var.get()
                        and self.restart_attempts < self.max_restart_attempts
                    ):
                        self.restart_attempts += 1
                        self.log_to_console(
                            f"🔄 Auto-restarting server "
                            f"(attempt {self.restart_attempts}/{self.max_restart_attempts})..."
                        )
                        self.root.after(0, self.restart_server)
                    else:
                        if self.restart_attempts >= self.max_restart_attempts:
                            self.log_to_console(f"Max restart attempts ({self.max_restart_attempts}) reached, giving up")
                        self.root.after(0, self.handle_server_crash)

                if self.last_server_status != server_running:
                    self.root.after(0, self.force_status_update)

                self.last_server_status = server_running

            except Exception as e:
                self.log_to_console(f"Error in monitor_server: {e}")

            time.sleep(5)