🦸‍♂️ Your Comics!

The ultimate, AI-powered comic book library manager. Comic Vault goes beyond just opening .cbz files—it uses Google's Gemini AI and the ComicVine API to organize, tag, summarize, and even read your comics to you.
Whether you're building massive Marvel reading orders, converting legacy .cbr files, or generating deep-dive audio podcasts about your favorite issues, Comic Vault is the all-in-one Swiss Army knife for digital comic collectors.

![splash_art](https://github.com/user-attachments/assets/18acda18-0bef-4b5b-8942-f6dfc28ecbfe)

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/e774b31c-c6f7-4d7d-a8d3-7d4263cffdb6" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9807c515-770b-483c-a544-132fd6aee293" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9e4b114a-23ef-4e4f-82ae-a640cc86386d" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/059cd074-0b02-486c-af44-6b83db268327" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9476e0dd-90f5-4270-a4f5-b456d0410e93" />
<img width="1065" height="789" alt="image" src="https://github.com/user-attachments/assets/d27ded42-54a6-4eb6-8768-8b328749f659" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/a66bbdd7-a345-47a2-af07-ca445b136830" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/809c403f-7f3a-4dae-9baa-ed3ff7af245d" />


✨ Core Features:

📚 Smart Library & Grid Viewer

Bulletproof File Parsing: An advanced regex engine that accurately reads chaotic scene release filenames, distinguishing between Volume numbers, Issue numbers, and Print Years.

Natural Sorting: Intelligently sorts files mathematically (Issue 2 comes before Issue 10), rather than alphabetically.

Lying Extension Detection: Automatically detects and safely extracts ZIP files disguised as RARs (and vice-versa) without crashing.

External Reader Integration: Instantly open any comic in your preferred reader (e.g., YACReader, CDisplayEx).

📋 AI Reading Lists (.cbl)

AI List Generator: Type "Marvel Civil War Main Event" and let Gemini build a 100% complete, chronological .cbl reading list.

Lightning Cache Grid: Opening a reading list instantly scans your hard drives to match files to the list. Matches are heavily cached, meaning massive 200-issue lists load in milliseconds on the second open!

Missing Issue Catcher: If you don't own an issue on the reading list, it displays a red "Missing" placeholder. Clicking it automatically opens the built-in browser and searches for the missing comic!

Strict Format & Year Guards: Ensures "Epic Collections" never steal slots meant for single issues, and rigorously checks ComicVine release years to keep timelines accurate.

🏷️ Batch Tagger & CBR Converter:

Auto-Matching: Point the app at a folder of untagged comics. It will ping ComicVine, find the exact metadata, and inject a perfectly formatted ComicInfo.xml into the file.

CBR to CBZ Conversion: Safely extracts legacy .cbr (RAR) archives and repacks them as modern, standardized .cbz (ZIP) files on the fly.

Interactive Mode: Review and confirm metadata matches before they are injected.

AI Metadata Fallback: If ComicVine doesn't have the data, Gemini AI will search the web and generate the ComicInfo.xml data from scratch!

🧠 AI Summaries & EPUB Export:

Deep-Dive Analysis: Generates rich, 500-800 word summaries of any issue, detailing Context, Plot, Key Moments, and Historical Significance.

Batch EPUB Export: Select an entire volume (e.g., Fantastic Four Vol 1-50) and generate a folder full of beautifully formatted .epub summary books, complete with cover art.

🎙️ "The Interrogator" (AI Audio & Chat):

Text-to-Speech (TTS) Engine: Uses high-quality Microsoft Edge Neural voices to read AI summaries to you out loud like a podcast.

Auto-Play: Kick back and let the app automatically play the summary of the next issue when the current one finishes.

Context-Aware Chat: Jump into the "Comic Chat" tab to talk directly to Gemini about the specific issue you are looking at. Ask it questions about characters, lore, or creative teams, and it will speak its answers back to you!

🌐 Built-In GetComics Browser:

Silent Browsing: A custom, ad-muting web engine profile built specifically for navigating GetComics without annoying console errors or popups.

Native Download Manager: Intercepts downloads directly inside the app with integrated progress bars.

🛠️ Installation & Setup:

Prerequisites

Python 3.10+

WinRAR/UnRAR: Required for extracting .cbr files. (Ensure UnRAR.exe is installed, usually in C:\Program Files\WinRAR\).

Python Dependencies

Install the required libraries using pip:

pip install PyQt6 PyQt6-WebEngine requests google-genai patool rarfile edge-tts markdown EbookLib


Configuration

On first launch, navigate to the Settings Tab and input:

ComicVine API Key: Get a free key from ComicVine.

Gemini API Key: Get a free key from Google AI Studio.

Reader Executable: Path to your preferred comic reader (e.g., C:\Program Files\YACReader\YACReader.exe).

(Note: API keys require an app restart to take effect).

🚀 Usage Guide

Building a Library: Go to the "Library" tab, click "+ Add Folder", and select your root comic drives.

Reading Lists: Drag and drop .cbz files into the Reading Tab to build custom lists, then click "💾 Make .cbl" to save them.

Fixing Missing Covers: If covers aren't loading, click "Clear Cache" in the Library tab. The app handles WebP, JPG, PNG, and ignores MacOS junk files automatically.

Batch Tagging: Go to the "Batch Tagger" tab, select a folder, and click Start. The background thread will safely process files without freezing the UI.

Built with PyQt6, Edge-TTS, and the Google Gemini API.on locks gracefully when dealing with temporary archive directories.
