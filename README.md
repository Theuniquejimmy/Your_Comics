# Your Comics, the ultimate comic book tool!

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
