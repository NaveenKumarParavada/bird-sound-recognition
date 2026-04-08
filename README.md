# bird-sound-recognition
🐦 BirdID Pro — Bird Sound Recognition Web App

A full-stack web application for identifying bird species from audio recordings using the **BirdNET deep learning model**. Upload an audio file, and the app will detect bird species present in the recording along with confidence scores, timestamps, habitat info, diet, migration patterns, and conservation status.

 📸 Features


| # | Feature | Description |
|---|---|---|
| 1 | **Audio Upload & Analysis** | Upload audio recordings in MP3, WAV, OGG, FLAC, or M4A format (up to 50 MB). Files are validated by both extension and binary header before processing. |
| 2 | **BirdNET-Powered Detection** | Leverages the Cornell Lab's BirdNET deep learning model via the `birdnetlib` Python wrapper to identify bird species directly from raw audio. |
| 3 | **Confidence Scoring** | Every detection is returned with a percentage confidence score. Only detections meeting the minimum threshold of 25% are surfaced to the user. |
| 4 | **Timestamped Detections** | Each detected bird call includes precise start and end timestamps (in seconds) within the audio recording. |
| 5 | **Rich Bird Info Database** | Detected species are enriched with curated data covering habitat, diet, migration behavior, IUCN conservation status, and a full ecological description. |
| 6 | **User Authentication** | Session-based login system with passwords securely hashed using Werkzeug's `generate_password_hash` and verified with `check_password_hash`. |
| 7 | **Analysis History** | Per-user history of all past analyses, stored in memory during the session and persisted as UUID-named JSON files for retrieval across routes. |
| 8 | **Audio Playback** | Uploaded audio files are served directly from the results page, allowing users to replay the original recording alongside the detected species. |
| 9 | **System Health Check** | A dedicated `/system-check` endpoint reports the status of BirdNET availability, analyzer initialization, folder permissions, and supported formats. |
| 10 | **Developer Test Route** | The `/simple-test` route provides a lightweight upload-and-analyze flow for rapid BirdNET functionality testing outside the full application UI. |



🧠 How It Works

1. User logs in and navigates to the **Analyze** page
2. An audio file is uploaded (validated by format and file header)
3. The file is passed to BirdNET's `Recording` + `Analyzer` classes with GPS coordinates and date
4. BirdNET segments the audio and returns detections with species names and confidence scores
5. Detections above the 25% confidence threshold are enriched with data from a built-in bird encyclopedia
6. Results are saved as JSON and displayed with full species details and audio playback



 🗂️ Project Structure
## Project Structure

```
bird-sound-recognition/
│
├── app.py                        # Core Flask application
│                                 # Handles routing, BirdNET integration,
│                                 # user authentication, and result persistence
│
├── tester.py                     # Standalone analysis script
│                                 # Used to test BirdNET detection
│                                 # outside of the web application
│
├── uploads/                      # Uploaded audio files
│                                 # Auto-created at runtime
│                                 # Files are timestamped to prevent collisions
│
├── results/                      # Analysis output files
│                                 # Each result stored as a UUID-named JSON file
│
├── templates/                    # Jinja2 HTML templates (server-rendered)
│   ├── login.html                # User login page
│   ├── dashboard.html            # User dashboard with recent analysis history
│   ├── analyze.html              # Audio upload and analysis form
│   ├── results.html              # Detection results with species info and playback
│   └── history.html             # Full per-user analysis history
│
├── static/
│   ├── css/                      # Application stylesheets
│   └── js/                       # Client-side scripts
│
└── README.md                     # Project documentation
```

### File Responsibilities

| File / Folder | Responsibility |
|---|---|
| `app.py` | Flask app factory, route definitions, BirdNET `Analyzer` initialization, audio validation, bird info lookup, session management, JSON persistence |
| `tester.py` | Minimal script to run `birdnetlib.Recording.analyze()` on a local audio file and print the highest-confidence detection |
| `uploads/` | Runtime storage for user-submitted audio files; filenames are prefixed with a `YYYYMMDD_HHMMSS` timestamp |
| `results/` | Stores one JSON file per analysis, keyed by a UUID, containing detections, metadata, and summary statistics |
| `templates/` | Server-rendered pages using Jinja2; no separate frontend build step required |
| `static/css/` | Stylesheets for all application pages |
| `static/js/` | JavaScript for client-side interactivity (e.g., bird info live lookup on the results page) |




🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| AI / ML | BirdNET (Cornell Lab), `birdnetlib` |
| Audio Processing | `birdnetlib` (internal), `pydub` (in tester) |
| Auth | Werkzeug (`generate_password_hash`, `check_password_hash`) |
| Storage | In-memory dict + JSON file persistence |
| Frontend | Jinja2 templates, HTML/CSS/JS |
| File Handling | `werkzeug.utils.secure_filename`, UUID-based naming |



⚙️ Installation

1. Clone the Repository

```bash
git clone https://github.com/your-username/birdid-pro.git
cd birdid-pro
```

 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

3. Install Dependencies

```bash
pip install flask birdnetlib pydub werkzeug
```

>  Note: BirdNET requires TensorFlow. `birdnetlib` will install it automatically, but ensure your Python version is compatible (3.8–3.11 recommended).

### 4. Run the Application

```bash
python app.py
```

App runs at: `http://localhost:5000`

---

🔐 Default Login Credentials

| Username | Password |
|---|---|
| `naveen` | `1234` |
| `admin` | `admin` |

> ⚠️ Change these credentials before deploying to production. Also update `SECRET_KEY` in `app.py`.

---

🎵 Supported Audio Formats

| Format | Extension |
|---|---|
| MP3 | `.mp3` |
| WAV | `.wav` |
| OGG Vorbis | `.ogg` |
| FLAC | `.flac` |
| M4A | `.m4a` |

Maximum file size: 50 MB


🌍 Location & Date Parameters

BirdNET uses GPS coordinates and recording date to improve species detection accuracy (accounts for species range and seasonal migration patterns).

Currently, the app uses **default coordinates** (lat: `35.4244`, lon: `-120.7463` — San Luis Obispo, CA). These are hardcoded in `app.py` and `tester.py`. A future improvement would be to allow users to input their own coordinates from the analyze form.

---

📖 Bird Information Database

The app includes a built-in encyclopedia of 40+ North American bird species, each with:

- Common & scientific name
- Habitat description
- Migration behavior
- Diet
- IUCN Conservation status
- Detailed description

Species covered include: American Robin, Black-capped Chickadee, American Crow, Mallard, Red-tailed Hawk, various warblers, woodpeckers, sparrows, thrushes, vireos, and more.

---

🧪 Standalone Tester (`tester.py`)

A lightweight script for testing BirdNET analysis outside of the web app:

python

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from datetime import datetime

analyzer = Analyzer()

recording = Recording(
    analyzer,
    "your_audio_file.mp3",
    lat=0,
    lon=-120.7463,
    date=datetime(year=2022, month=5, day=10),
    min_conf=0.25,
)
recording.analyze()

if recording.detections:
    best = max(recording.detections, key=lambda x: x['confidence'])
    print(best)
else:
    print("No detections found.")




🔌 API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET/POST | `/login` | ❌ | Login page |
| GET | `/logout` | ✅ | Logout and clear session |
| GET | `/dashboard` | ✅ | User dashboard with recent history |
| GET/POST | `/analyze` | ✅ | Upload audio and run analysis |
| GET | `/results/<id>` | ✅ | View results for a specific analysis |
| GET | `/history` | ✅ | Full analysis history for user |
| GET | `/uploads/<filename>` | ❌ | Stream an uploaded audio file |
| GET | `/api/analysis/<id>` | ✅ | JSON result for an analysis |
| GET | `/api/bird-info/<name>` | ✅ | JSON bird info by scientific name |
| GET | `/system-check` | ✅ | Health check — BirdNET status, folder access |
| GET | `/test-birdnet` | ✅ | Quick BirdNET analyzer test |
| GET/POST | `/simple-test` | ✅ | Simple upload + analyze test route |

---

🚀 Future Improvements

- [ ] Dynamic GPS coordinates from user input or geolocation API
- [ ] Persistent database (SQLite / PostgreSQL) instead of in-memory storage
- [ ] Spectrogram visualization of audio
- [ ] Export results as CSV or PDF
- [ ] Map view showing where recordings were made
- [ ] Support for batch file uploads
- [ ] Docker containerization for easy deployment
- [ ] Real-time confidence threshold slider

---

📄 License

This project is for educational and research purposes. BirdNET model usage is subject to the [Cornell Lab BirdNET license](https://github.com/kahst/BirdNET-Analyzer).

---

🙏 Acknowledgements

- [BirdNET-Analyzer](https://github.com/kahst/BirdNET-Analyzer) by the Cornell Lab of Ornithology & Chemnitz University of Technology
- [birdnetlib](https://github.com/joeweiss/birdnetlib) — Python wrapper for BirdNET
- [Flask](https://flask.palletsprojects.com/) — Web framework
- [Xeno-canto](https://xeno-canto.org/) — Source of sample audio recordings used for testing
