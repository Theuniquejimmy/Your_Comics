🦸‍♂️ Your Comics!

Your Comics is a powerful, fully-featured desktop application for managing, tagging, and exploring your digital comic collection. Built with PyQt6, it combines lightning-fast local library management with the deep lore of Comic Vine and the analytical power of Google's Gemini AI.
Whether you are mapping complex reading orders, converting legacy CBRs, generating deep-dive audio summaries, or just trying to get your ComicInfo.xml tags perfect, this app does it all.

![splash_art](https://github.com/user-attachments/assets/18acda18-0bef-4b5b-8942-f6dfc28ecbfe)

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/80408c1a-9a33-4bc0-9881-311329ab7cdb" />
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

📚 Library & Grid Management:

Lightning-Fast Caching: Automatically generates and saves tiny, high-speed thumbnails (using background threads) so massive folders load instantly.

Persistent Hide System: Right-click to permanently banish junk folders, text files, or unwanted comics from your library view.

Dynamic Navigation: Seamlessly jump in and out of folders directly from the Grid view with intuitive Up and Forward controls.

Custom Covers: Right-click any comic or folder to assign a custom image, extract a specific page from inside the archive, or copy a cover from another comic.

📋 The CBL Heuristic Engine:

Smart Reading Lists: Import .cbl (Comic Book List) files and watch the app intelligently map your local files to the required issues.

Advanced Name Parsing: Automatically handles messy archive formats (including URL-encoded characters, Novus release tags like (_02), and mismatched dates).

The "Double Shield": Mathematically prevents Single Issues from stealing TPB/Omnibus slots, and applies lethal penalties to files with wildly inaccurate years.

Missing Issue Tracker: Visually displays which issues you own and which you are missing. Clicking a missing issue instantly searches the web for it.

🤖 AI Integration (Powered by Gemini 2.5):

AI List Maker: Ask Gemini to build exhaustive, chronologically accurate reading orders for massive crossover events (e.g., "Marvel Civil War Main Event").

AI Metadata Tagger: Paste a wiki URL or type a comic name, and Gemini will scrape the web to generate a perfect, ComicRack-compatible metadata payload.

The Interrogator (Comic Chat): An integrated AI assistant that reads the context of your currently selected comic and answers deep-lore questions about the universe. Includes Edge TTS voice responses.

Deep-Dive Summaries: Generates 500-word, highly detailed plot summaries and significance analyses for any issue.

EPUB Export: Batch-generate AI summaries for entire runs and compile them into a readable EPUB book.

🏷️ Intelligent Batch Tagger:

Comic Vine Integration: Connects directly to the Comic Vine API to pull Characters, Teams, Locations, Story Arcs, Writers, and Artists.

CBR to CBZ Conversion: Safely extracts legacy .cbr (RAR) archives and repackages them as universal .cbz (ZIP) files while injecting metadata.

Forced Volume Locking: Paste a Comic Vine URL into the tagger to lock the engine to a specific volume database ID, bypassing fuzzy search errors entirely.

Interactive Mode: Allows you to manually confirm matches and covers before altering files.

🌐 Built-in Web Browser:

GetComics Integration: A fully integrated PyQt6 WebEngine browser to hunt for missing issues.

Ad-Silencer: Custom web page profiles actively suppress noisy javascript console logs.

Native Downloader: Intercepts browser downloads and saves files directly to your library with visual progress bars.



🛠️ Prerequisites & Installation:

1. Run the exe and that’s t!

or

1. System Requirements

Python 3.9+

WinRAR / UnRAR: Required for handling .cbr files. Ensure UnRAR.exe is installed (default path: C:\Program Files\WinRAR\UnRAR.exe).

External Reader (Optional): Designed to hook into external readers like YACReader.

2. Python Dependencies

Install the required Python libraries via pip:

pip install PyQt6 PyQt6-WebEngine requests urllib3
pip install google-genai edge-tts ebooklib markdown
pip install rarfile patool


3. API Keys

To unlock the full potential of the app, you need two free API keys:

Comic Vine API Key: Get one at Comic Vine API.

Google Gemini API Key: Get one at Google AI Studio.

Note: You can input these keys directly in the Settings tab of the application.

🚀 How to Use

Launch the App: Run python yourcomics.py (or whatever your main script is named).

Add Libraries: Go to the Library tab on the left panel and click + Add Folder to link your comic hard drives.

Set Up Settings: Navigate to the far-right Settings tab. Input your API keys, select your preferred AI Narrator voice, and link your external reader executable. (Restart the app to apply API keys).

Tagging Comics:

Single: Click a comic in the Grid, view its details, and click "Convert/Tag".

Batch: Go to the Batch Tagger tab, add a folder, and let the engine scan and tag your entire collection automatically.

Reading Lists: Drag and drop comics into the Reading tab, or use the List Maker to have AI generate a .cbl file for you.

⚠️ Known Issues & Notes

CBR Extraction Limits: Extracting .cbr files relies heavily on the rarfile and patoolib wrappers for your system's native UnRAR installation. If CBR conversions fail, ensure WinRAR is installed correctly.

Metadata Overwrites: CBZ files are ZIP archives. The app safely rewrites the archive into a temporary memory stream when updating ComicInfo.xml to prevent file corruption.

TTS Generation: Generating audio via edge-tts requires an active internet connection.

Built with Python, PyQt6, and comic book love.
