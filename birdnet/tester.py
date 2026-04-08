from pydub import AudioSegment
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from datetime import datetime

# Convert .ogg to .mp3
# audio = AudioSegment.from_ogg("XC128013.ogg")
# audio.export("sample.mp3", format="mp3")

# Load and initialize the BirdNET-Analyzer models.
analyzer = Analyzer()

recording = Recording(
    analyzer,
    "XC558716 - Soundscape.mp3",
    lat=0,
    lon=-120.7463,
    date=datetime(year=2022, month=5, day=10), # use date or week_48
    min_conf=0.25,
)
recording.analyze()

# Find the detection with the highest confidence
if recording.detections:
    highest_confidence_detection = max(recording.detections, key=lambda x: x['confidence'])
    print(highest_confidence_detection)
else:
    print("No detections found.")