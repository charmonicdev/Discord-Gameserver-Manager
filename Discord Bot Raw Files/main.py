# main.py
# Entry point – wires ServerManager into BotGUI and starts the tkinter loop.

import tkinter as tk

from gui import BotGUI
from server_manager import ServerManager


class App(ServerManager, BotGUI):
    """
    Combines the GUI (BotGUI) with server process management (ServerManager).

    Python MRO means ServerManager methods are resolved before BotGUI,
    but BotGUI.__init__ is the one that sets everything up and is called here.
    """
    def __init__(self, root):
        BotGUI.__init__(self, root)


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
