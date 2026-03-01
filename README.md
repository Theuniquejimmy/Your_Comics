🦸 Your Comics!

An AI-Powered Local Comic Book Librarian, Tagger, & Reader

Welcome to Your Comics!, a comprehensive, locally-hosted desktop application built in Python and PyQt6. This app is designed to be the ultimate hub for organizing, reading, and exploring your comic book collection. It combines local file management with powerful integrations like the Comic Vine API and Google's Gemini AI to act as your personal comic book historian, automated archivist, and reading companion.

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/e774b31c-c6f7-4d7d-a8d3-7d4263cffdb6" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9807c515-770b-483c-a544-132fd6aee293" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/b1a0b3c8-8098-4d2f-9f5a-da2f375c9e83" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/059cd074-0b02-486c-af44-6b83db268327" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9476e0dd-90f5-4270-a4f5-b456d0410e93" />
<img width="1065" height="789" alt="image" src="https://github.com/user-attachments/assets/d27ded42-54a6-4eb6-8768-8b328749f659" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/a66bbdd7-a345-47a2-af07-ca445b136830" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/809c403f-7f3a-4dae-9baa-ed3ff7af245d" />

✨ Key Features:

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

    Web Search: Browse and download new comics directly inside the app.

    Batch Tagger: Select a folder of untagged comics to convert, verify, and tag them all.

    Your fully compiled yourcomics.exe will be waiting for you inside the newly created dist folder!
