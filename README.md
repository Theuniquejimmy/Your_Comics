🦸 Your Comics!

An AI-Powered Local Comic Book Librarian, Tagger, & Reader

Welcome to Your Comics!, a comprehensive, locally-hosted desktop application built in Python and PyQt6. This app is designed to be the ultimate hub for organizing, reading, and exploring your comic book collection. It combines local file management with powerful integrations like the Comic Vine API and Google's Gemini AI to act as your personal comic book historian, automated archivist, and reading companion.

✨ Key Features:

    🏷️ Automated Batch Tagger & CBR Converter: Point the app at a folder of messy .cbz or .cbr files. It will automatically parse the filenames, find the correct issue on Comic Vine, and permanently inject a universal ComicInfo.xml metadata file into the archive. It even extracts and completely converts .cbr (RAR) files into standard .cbz (ZIP) files automatically!

    🕵️ Interactive Cover Verification: When tagging in Interactive Mode, a 3-pane pop-up window allows you to compare your actual local comic cover side-by-side with the Comic Vine cover before approving the metadata injection, ensuring 100% accuracy for your library.

    🤖 "The Interrogator" AI Chat: Chat directly with an embedded Gemini AI assistant about any comic in your library. Ask for lore, backstory, or character histories, and have the answers read aloud to you using integrated Text-to-Speech (TTS).

    🎙️ Voiced Summaries: Use the Comic Finder to pull metadata from Comic Vine, generate AI summaries, and listen to an audio briefing. Includes full media controls (Play, Pause, Stop) and customizable voice/speed settings.

    🌐 Built-In Web Browser: A fully functional Chromium-based web browser locked to getcomics.info. Download comics directly into your library with a built-in download manager and progress tracker. All native ad-scripts and console errors are muted for a clean experience.

    ⚙️ UI-Driven Settings: No need to hardcode API keys! Manage your Comic Vine API key, Gemini API key, AI voice preferences, and .exe reader paths directly from the Settings tab.


🛠️ Prerequisites & Setup

Before running the application, you will need a few free keys and tools:

    Comic Vine API Key: Used to pull down comic covers, issue descriptions, and metadata. (Get one at comicvine.gamespot.com/api)

    Gemini API Key: Used to power "The Interrogator" AI chat and summaries. (Get one at Google AI Studio)

    WinRAR or 7-Zip: Must be installed on your Windows machine to allow the app to extract and convert .cbr files.

Note: You can enter your API keys directly into the app's Settings Tab on your first launch!
📦 Installation

Ensure you have Python 3.9+ installed on your machine. Open your terminal or command prompt and install the required dependencies:
Bash

pip install PyQt6 PyQt6-WebEngine google-generativeai requests markdown edge-tts patool

🚀 Usage

To launch the application from your terminal, simply navigate to the folder containing your script and run:
Bash

python yourcomics.py

Navigating the App:

    Local Details / Grid: Browse your local files using a dark-mode directory tree. View high-res covers, or browse your collection visually in the Grid tab. Hit Ctrl+Enter to instantly open any comic in your external reader.

    Comic Finder: Analyze a selected comic, fetch its data, generate an AI summary, and listen to the audio briefing.

    Comic Chat: Click ✨ AI Info anywhere in the app to instantly ask the AI about the selected comic.

    🌐 Web Search: Browse and download new comics directly inside the app.

    🏷️ Batch Tagger: Select a folder of untagged comics to automatically convert CBRs to CBZs and inject ComicInfo.xml metadata.

    ⚙️ Settings: Configure your API keys, text-to-speech voices, and default comic reader application.

🏗️ Building a Standalone Executable (.exe)

If you want to turn this Python script into a native Windows application that you can double-click without opening a terminal, package it using PyInstaller:

    Install PyInstaller:

    pip install pyinstaller

    Build the app (this hides the background console and bundles everything into one file):

    pyinstaller --noconsole --onefile yourcomics.py
    Bash

    Your fully compiled yourcomics.exe will be waiting for you inside the newly created dist folder!

    Or just downlaod me ready made exe!
