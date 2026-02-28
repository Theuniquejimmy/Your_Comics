🦸 Your Comics!

An AI-Powered Local Comic Book Librarian & Reader

Welcome to Your Comics!, a comprehensive, locally-hosted desktop application built in Python and PyQt6. This app is designed to be the ultimate hub for organizing, reading, and exploring your comic book collection. It combines local file management with powerful integrations like the Comic Vine API and Google's Gemini AI to act as your personal comic book historian and assistant.
✨ Key Features

    📚 Local Library Management: Browse your local comic files using a sleek dark-mode directory tree. View high-res covers and metadata in the Details tab, or browse your collection visually in the Grid tab.

    🤖 "The Interrogator" AI Chat: Chat directly with an embedded Gemini AI assistant about any comic in your library. Ask for lore, backstory, or character histories, and have the answers read aloud to you using integrated Text-to-Speech (TTS).

    🎙️ Voiced Summaries: Use the Comic Finder to pull metadata from Comic Vine, generate AI summaries, and listen to an audio briefing. Includes full media controls (Play, Pause, Stop) and customizable voice/speed settings.

    🌐 Built-In Web Browser: A fully functional Chromium-based web browser locked to getcomics.info. Download comics directly into your library with a built-in download manager and progress tracker.

    📖 External Reader Integration: Launch comics instantly in your preferred desktop reader (like YACReader) with a single keystroke (Ctrl+Enter).

    ⚙️ UI-Driven Settings: No need to hardcode API keys! Manage your Comic Vine API key, Gemini API key, AI voice preferences, and .exe reader paths directly from the Settings tab.

🛠️ Prerequisites & Setup

Before running the application, you will need to get two free API keys:

    Comic Vine API Key: Used to pull down comic covers, issue descriptions, and metadata. (Get one at comicvine.gamespot.com/api)

    Gemini API Key: Used to power "The Interrogator" AI chat and summaries. (Get one at Google AI Studio)

Note: You can enter these keys directly into the app's Settings Tab on your first launch!
📦 Installation

Ensure you have Python 3.9+ installed on your machine. Open your terminal or command prompt and install the required dependencies:
Bash

pip install PyQt6 PyQt6-WebEngine google-generativeai requests markdown edge-tts

(If you used any additional libraries for EPUB generation or metadata, ensure they are installed here as well).
🚀 Usage

To launch the application from your terminal, simply navigate to the folder containing your script and run:
Bash

python yourcomics.py

Navigating the App:

    Left Panel: Use the file tree to navigate your hard drive and select comic files.

    Local Details / Grid: View the currently selected folder or file.

    Comic Finder: Analyze a selected comic, fetch its Comic Vine data, generate an AI summary, and listen to the audio briefing.

    Comic Chat: Click ✨ AI Info anywhere in the app to instantly ask the AI about the selected comic.

    Web Search: Browse and download new comics.

    Settings: Configure your API keys, text-to-speech voices, and default comic reader application.

🏗️ Building a Standalone Executable (.exe)

If you want to turn this Python script into a native Windows application that you can double-click without opening a terminal, you can package it using PyInstaller.

    Install PyInstaller:
    Bash

    pip install pyinstaller

    Build the app (this hides the background console and bundles everything into one file):
    Bash

    pyinstaller --noconsole --onefile yourcomics.py

    Your fully compiled yourcomics.exe will be waiting for you inside the newly created dist folder!# Your Comics, the ultimate comic book tool!

A powerhouse offline comic book library manager supercharged with modern AI, text-to-speech capabilities, and seamless web scraping. This application bridges the gap between a lightweight local file browser and an advanced comic research tool.

## ✨ Features

### 📚 Intelligent Library Management
* **Dual-View Browsing:** Navigate your massive comic collection using a clean directory tree, or switch to the **Local Grid** tab to view beautiful, smoothly scaled cover thumbnails for an entire folder.
* **Lightning-Fast Image Caching:** Background threads silently extract covers and save them to a hidden `.comic_cache` folder. Once a folder is loaded once, it loads instantly the next time without freezing your computer.
* **Smart Search:** An instant-filter search bar seamlessly hides folders and grid icons that don't match your query as you type.
* **Reading History:** A dedicated "Reading" tab automatically tracks your recently opened comics, complete with thumbnail icons, a clear-all button, and a right-click menu to remove specific issues.
* **Custom Libraries:** Save your favorite or most-visited folders as quick-access shortcuts at the top of the browser.

### ⚙️ Conversion & Reading
* **One-Click YACReader Integration:** Instantly launch the currently selected `.cbz` or `.cbr` file directly into YACReader for a seamless reading experience.
* **Automated CBR to CBZ Conversion:** A background worker physically extracts RAR-based `.cbr` archives, injects fresh XML metadata, and safely repackages them into standard `.cbz` files.
* **Live Progress Tracking:** Visual progress bars and status updates tell you exactly what the converter is doing (Extracting, Generating Metadata, Zipping) without locking up the UI.

### 🌐 Comic Vine Web Scraping & Audio
* **Deep-Dive Issue Search:** The **Comic Finder** tab plugs directly into the Comic Vine API, allowing you to search for specific volumes, select an issue, and pull down its official cover, writer, and artist credits.
* **EPUB Generation:** Export detailed AI summaries and covers directly into perfectly formatted `.epub` files for reading on other devices.
* **Batch Processing:** Tell the app to look at a range of issues, and it will automatically scrape the data, generate AI summaries, and export a folder full of EPUBs.
* **Integrated Edge TTS Audio:** Listen to your comic summaries out loud! Choose from a variety of built-in voice models, adjust the playback speed, and play/stop the audio directly inside the app.

### 🤖 Gemini AI Assistant
* **Context-Aware Comic Chat:** The **Comic Chat** tab serves as your personal comic historian. If you have an issue selected, the AI automatically knows what you are looking at and can answer deep-dive questions about the plot, characters, or significance of that exact comic.
* **Dynamic Story Summaries:** Passes scraped plot data and character lists to Gemini to dynamically generate 500-800 word historical summaries of single issues.

## 🛠️ Requirements & Setup

This application requires Python 3.x and the following libraries:

```bash
pip install PyQt6 rarfile requests edge-tts markdown google-genai EbookLib

```

**Additional System Requirements:**

* **UnRAR:** To process `.cbr` files, you must have `unrar.exe` installed on your system (usually included with WinRAR at `C:\Program Files\WinRAR\UnRAR.exe`).

## 🔑 API Keys

To use the AI and web scraping features, you need to set the following Environment Variables on your system:

* `COMIC_VINE_KEY`: Your personal Comic Vine API key.
* `GEMINI_KEY`: Your Google Gemini API key.

## 🚀 Usage

Run the main Python script from your terminal to launch the application:

```bash
python comic.py


```
