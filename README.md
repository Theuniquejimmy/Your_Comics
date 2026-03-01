🦸 Your Comics!

A powerful, automated desktop application built with Python and PyQt6 for managing, tagging, and enhancing digital comic book collections. This tool seamlessly integrates with the Comic Vine API to fetch highly accurate metadata, converts legacy formats, injects standard `ComicInfo.xml` data, and uses AI to generate narrated summaries of your favorite issues.

<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/e774b31c-c6f7-4d7d-a8d3-7d4263cffdb6" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9807c515-770b-483c-a544-132fd6aee293" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9e4b114a-23ef-4e4f-82ae-a640cc86386d" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/059cd074-0b02-486c-af44-6b83db268327" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/9476e0dd-90f5-4270-a4f5-b456d0410e93" />
<img width="1065" height="789" alt="image" src="https://github.com/user-attachments/assets/d27ded42-54a6-4eb6-8768-8b328749f659" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/a66bbdd7-a345-47a2-af07-ca445b136830" />
<img width="1628" height="1103" alt="image" src="https://github.com/user-attachments/assets/809c403f-7f3a-4dae-9baa-ed3ff7af245d" />


## 🚀 Key Features:

* **Smart Metadata Tagging:** Automatically identifies comic books and injects standardized `ComicInfo.xml` metadata directly into your archives for perfect compatibility with readers like ComicRack, Kavita, and Komga.
* **CBR to CBZ Conversion:** On-the-fly, lossless extraction and repacking of legacy `.cbr` (RAR) archives into the modern, widely supported `.cbz` (ZIP) format.
* **Hybrid Two-Step Search Engine:** Bypasses standard API limitations by utilizing a custom hybrid search algorithm—fuzzy searching for volume names and applying strict filters for issue numbers—guaranteeing perfectly matched metadata.
* **AI Comic Summaries:** Integrates with generative AI to produce detailed, spoiler-free summaries and overviews of specific issues.
* **Integrated TTS Audio Player:** Turns your comic summaries into an audiobook experience using Edge TTS, complete with adjustable playback speeds, pause/resume functionality, and an "Auto-Play Next Issue" queue.
* **EPUB Export:** Instantly compile your AI-generated summaries and Comic Vine cover art into a cleanly formatted EPUB book.
* **Batch Processing:** Point the app at an entire directory of untagged comics and let the multi-threaded batch processor clean, convert, and tag them automatically while you monitor the progress bar.
* **Interactive Match Resolution:** A dedicated UI pane for resolving metadata conflicts, allowing users to manually view covers and select the correct Comic Vine entry before injecting data.

## 🛠️ Technologies Used:

* **Python:** Core application logic and multi-threading.
* **PyQt6:** Modern, responsive graphical user interface.
* **Comic Vine API:** The primary database for scraping comic covers, credits, release years, and publisher data.
* **Patool / Zipfile:** For cross-platform archive extraction and `.cbz` repacking.
* **Edge TTS & QtMultimedia:** For generating and playing real-time audio narration.

## ⚙️ Prerequisites & Setup:

**To run this application locally, you will need to set up your environment and obtain the necessary API keys.

Download the ready made exe!!**

or

1. **Clone the repository:**
```bash
git clone https://github.com/YourUsername/Comic-Vault-Analyzer.git
cd Comic-Vault-Analyzer

```


2. **Install required dependencies:**
```bash
pip install -r requirements.txt

```

3. **Configure API Keys:**
* Obtain a free API key from [Comic Vine](https://comicvine.gamespot.com/api/).
* *(If applicable)* Obtain your AI Provider API key for the summary generation.
* Add these keys to your environment variables or a `.env` file as specified in the configuration module.

## 📖 How to Use

### The Batch Tagger

1. Navigate to the **Batch Tagger** tab.
2. Select a folder containing your `.cbz` or `.cbr` files.
3. The application will scan the filenames, extract the series name, issue number, and year (e.g., stripping padded zeros and handling scene tags automatically).
4. Watch the progress as it fetches data, converts CBRs, and injects `ComicInfo.xml` files.

### The Comic Finder & Reader

1. Navigate to the **Comic Finder** tab.
2. Search for a Volume (e.g., "The Amazing Spider-Man").
3. Select the correct volume from the chronologically sorted dropdown.
4. Enter an issue number and click **Analyze Single Issue**.
5. The app will fetch the official cover art, generate a written summary, and offer TTS playback controls to read it aloud to you. Toggle **Auto-Play Next** to listen to an entire run seamlessly.

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change. Please ensure your code handles Windows file permission locks gracefully when dealing with temporary archive directories.
