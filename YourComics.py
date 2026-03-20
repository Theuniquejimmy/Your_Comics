"""
ComicVault - Backward-compatible launcher.

This file exists for backward compatibility. The application has been refactored
into a modular architecture. Run via: python main.py

Module structure:
  - main.py      : Entry point
  - config.py    : Settings, constants, API keys
  - utils.py     : Utility functions (parsing, XML generation, etc.)
  - workers.py   : Background threads (ComicVine, AI, conversion, etc.)
  - widgets.py   : Custom Qt widgets
  - app_ui.py    : Dialogs, tabs, and main window
"""
if __name__ == "__main__":
    from main import main
    main()
