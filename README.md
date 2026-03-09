🦸‍♂️ Your Comics! (Ultimate Comic Manager)

Your Comics! is a lightning-fast, highly advanced desktop application for comic book readers, collectors, and historians. Built with PyQt6, it combines local file management, intelligent metadata tagging, automated .cbl (Reading List) mapping, and cutting-edge AI integrations.
Whether you are managing massive crossover events, converting CBRs, or having an AI read you a deep-dive history of your favorite issue, this app does it all.

![splash_art](https://github.com/user-attachments/assets/18acda18-0bef-4b5b-8942-f6dfc28ecbfe)

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/e774b31c-c6f7-4d7d-a8d3-7d4263cffdb6" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/cce6d9ab-ca1d-4ba6-b802-334f2049524b" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/18350879-cb13-41ae-b745-ca8877d8c935" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/40cd456e-d097-4dc1-8320-17566a76bab7" />
<img width="1657" height="1103" alt="image" src="https://github.com/user-attachments/assets/a08e06fe-843d-4cbc-b011-b492755f46f6" />
<img width="1657" height="1103" alt="image" src="https://github.com/user-attachments/assets/3f19d505-5e23-4a98-9890-3e4bcff8d0ea" />
<img width="1065" height="789" alt="image" src="https://github.com/user-attachments/assets/29f2cf58-2350-45d6-9beb-67bfee35ae97" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/eaf77c54-33cf-43ed-93e2-7b2774331552" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/3a9da141-65d0-482d-9599-c5f3ae616fb6" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/2f098eed-464e-4bf8-81cb-97789cc331e4" />


✨ Features:



📁 Smart Library & Grid Management:


3D Folder Stacks: Folders are visually represented as dynamic 3D stacks, automatically digging into subfolders to display the #1 covers of the series contained inside.

Infinite Image Memory: PyQt's memory limit has been completely removed, allowing the app to process massive, high-res, or AI-upscaled comic pages without crashing.

Locked Grid Layout: Grid icons are completely locked into place, preventing accidental dragging or dropping while navigating.

Reading History Tracking: Both local comic files and .cbl Reading Lists are automatically pinned to your Reading History tab (with visual icons) so you can easily pick up where you left off.


🏷️ Intelligent Metadata Tagging:


Lightning-Fast CBZ Streaming: Injecting metadata into .cbz files no longer requires extracting data to your hard drive. The app streams the zip in-memory, updating metadata in less than a second.

Auto CBR to CBZ Conversion: Automatically extracts .cbr archives (via rarfile or patoolib) and repacks them cleanly into .cbz format during the tagging process.

Advanced Event Mapping: Scrapes ComicVine not just for Writers and Artists, but also automatically captures Story Arcs, Crossover Event Names (AlternateSeries), and Reading Order Numbers.

Multi-Folder Batch Tagging: Add multiple folders to the Batch Queue at once. Features an Interactive Mode to manually confirm tricky matches or inject AI data.


📚 Reading Lists (.CBL) & Auto-Mapping:


The "Collection Free-Pass" Engine: Intelligently maps local files to downloaded .cbl files. It knows the difference between single issues and "Epic Collections" or "Omnibuses", safely ignoring reprint year penalties and long subtitles.

Format Clash Guards: Strictly prevents a single issue from filling a slot meant for an Omnibus, and vice versa.

Missing Comic Web Search: Missing comics appear in the grid as red ❌. Clicking them automatically strips the year from the title, opens the built-in web browser, and searches GetComics.info for the exact issue.

Smart-Link: Right-click any slot on a .cbl grid to manually link a local file to it.

Export to CBL: Right-click any folder in your library to instantly generate a clean .cbl file from its contents.


🤖 AI Integration (Gemini 2.5) & Audio:


AI List Maker: Tell the AI (e.g., "Make a Marvel Civil War reading order") and it will search the web, compile a comprehensive list, and let you export it directly to a .cbl file.

Deep-Dive Summaries: Generates 500-800 word historical essays on any selected comic, detailing the context, plot, and significance.

Batch EPUB Export: Export AI summaries into standalone .epub books. (Can run in batches for entire volumes).

The Interrogator (Chat): Chat directly with the AI about the currently selected comic.

Edge-TTS Narrator: The app speaks AI summaries and chat responses aloud using high-quality neural voices. Features Play, Pause, Stop, custom Speed Sliders, and an "Auto-Play Next Issue" toggle!


🖼️ Ultimate Cover Customization:


Right-click any comic or folder in the grid to customize its display art! Your custom covers are saved safely in a local cache without altering your original files.

Pick Custom Image: Browse your PC for a .jpg or .png.

Pick Comic as Cover: Select a different .cbz file, and the app will automatically steal its cover to use as a folder poster.

Change Cover (Select Internal): Opens a beautiful visual UI. For files, it lets you pick from the first 15 pages (great for skipping blank covers). For folders, it deep-scans the directory and lets you pick from the #1 issues inside!

Reset to Default: Instantly clears overrides and re-extracts the original cover.


🛠️ Installation & Setup:

1. Run YourComics.exe

or

1. Install Python 3.9+

2. Install Required Packages:
Open your terminal or command prompt and run:

pip install PyQt6 PyQt6-WebEngine requests google-genai edge-tts markdown ebooklib patoolib rarfile


3. API Keys (Required for Metadata & AI features):
Open the application, navigate to the Settings tab, and input your API keys:

ComicVine API Key: Obtainable for free with a ComicVine account.

Gemini API Key: Obtainable for free via Google AI Studio.
(Note: Restart the app after adding your keys for the first time).

4. Optional Dependencies:

WinRAR / UnRAR: Required for parsing .cbr files natively. If not installed, the app will attempt to fallback to patoolib.

YACReader: The default external reader. You can change the executable path in the Settings tab if you prefer ComicRack, CDisplayEx, etc.


💡 Quick Tips:


The AI Fallback: If a comic isn't on ComicVine, paste the URL of a wiki page into the ComicVine search bar (or leave it with the filename info) and click "🤖 Add AI Info". The AI will scrape the webpage and perfectly format the metadata into your .cbz file.

Delete from List: Select items in your Reading List or List Maker tab and hit the Delete or Backspace key on your keyboard to instantly remove them.

Clear Cache: If images ever look wrong or outdated, go to the Library tab and click "Clear Cache" to force the app to redraw everything.
