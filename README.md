🦸 Your Comics!

An AI-Powered Local Comic Book Librarian, Tagger, & Reader

Welcome to Your Comics!, a comprehensive, locally-hosted desktop application built in Python and PyQt6. This app is designed to be the ultimate hub for organizing, reading, and exploring your comic book collection. It combines local file management with powerful integrations like the Comic Vine API and Google's Gemini AI to act as your personal comic book historian, automated archivist, and reading companion.
✨ Key Features
🏷️ The Ultimate Batch Tagger & CBR Converter

    Automated Metadata Injection: Point the app at a folder of messy files. It parses filenames, searches Comic Vine, and permanently injects a universal ComicInfo.xml metadata file into the archive.

    On-the-Fly CBR Conversion: Automatically extracts legacy .cbr (RAR) files and repacks them into standard .cbz (ZIP) files with live percentage tracking milestones so you never have to wonder if the app is frozen.

🕵️ Interactive Cover Verification

    3-Pane Matcher UI: Compare your actual local comic cover (extracted seamlessly in the background) side-by-side with the remote Comic Vine cover before approving the tag.

    Expanded Manual Search: If the auto-search fails, use the built-in search bar to manually query Comic Vine, pulling down up to 50 results at a time without ever leaving the verification window.

    🤖 AI Metadata Generator: If a comic isn't on Comic Vine, hit the "Add AI Info" button. The app will ping gemini-2.5-flash to hallucinate a perfectly formatted, standard JSON payload—including Writer and Artist credits—and inject it directly into your .cbz!

🤖 AI Companions & Audio

    "The Interrogator" AI Chat: Chat directly with an embedded Gemini AI assistant about any comic in your library. Ask for lore, backstory, or character histories.

    Voiced Summaries: Pull metadata from Comic Vine, generate AI summaries, and listen to an audio briefing using Text-to-Speech (TTS) with full media controls.

🌐 Built-In Web Browser & Settings

    Integrated Downloader: A fully functional Chromium-based web browser locked to getcomics.info. Download comics directly into your library with a built-in download manager and progress tracker.

    UI-Driven Settings: Manage your Comic Vine API key, Gemini API key, AI voice preferences, and .exe reader paths directly from the UI without touching the code.

🛠️ Prerequisites & Setup

Before running the application, you will need:

    Comic Vine API Key: Used to pull down comic covers and metadata. (Get one at comicvine.gamespot.com/api)

    Gemini API Key: Powers the AI Chat, summaries, and the AI Metadata Fallback. (Get one at Google AI Studio)

    WinRAR or 7-Zip: Must be installed on your Windows machine to allow the patool library to extract and convert .cbr files.

Note: You can enter your API keys directly into the app's Settings Tab on your first launch!
📦 Installation

Ensure you have Python 3.9+ installed on your machine. Open your terminal or command prompt and install the required dependencies:
Bash

pip install PyQt6 PyQt6-WebEngine google-generativeai requests markdown edge-tts patool

🚀 Usage

To launch the application from your terminal, navigate to the folder containing your script and run:
Bash

python yourcomics.py

Navigating the App:

    Local Details / Grid: Browse your files using a dark-mode directory tree. View high-res covers, or browse visually in the Grid tab. Hit Ctrl+Enter to open any comic in your external reader.

    Comic Finder: Analyze a selected comic, fetch its data, and listen to the audio briefing.

    Comic Chat: Click ✨ AI Info anywhere in the app to instantly ask the AI about the selected comic.

    🌐 Web Search: Browse and download new comics directly inside the app.

    🏷️ Batch Tagger: Select a folder of untagged comics to convert, verify, and tag them all.

🏗️ Building a Standalone Executable (.exe)

If you want to turn this Python script into a native Windows application without a background console, package it using PyInstaller:

    Install PyInstaller:
    Bash

    pip install pyinstaller

    Build the app (forcing the inclusion of the web browser core):
    Bash

    pyinstaller --noconsole --onefile --hidden-import PyQt6.QtWebEngineCore yourcomics.py

    Your fully compiled yourcomics.exe will be waiting for you inside the newly created dist folder!
