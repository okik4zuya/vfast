import argparse
import os
import json
from transcribr import Transcribr

parser = argparse.ArgumentParser(description="Transcribe local video file")

parser.add_argument("video_file", help="Video file path")

args = parser.parse_args()

video_file = args.video_file

# Get filename without extension for output
filename = video_file

# Transcribe local video
transcribr = Transcribr(model="tiny")
transcribr.transcribe(video_file)

# Get transcript data
transcript_data = transcribr.get_transcript()  # Assuming this method exists

# Save JSON with timestamps
json_path = os.path.join(f"transcript_{filename}.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(transcript_data, f, indent=4, ensure_ascii=False)

# Save TXT without timestamps
txt_path = os.path.join(f"transcript_{filename}.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    for item in transcript_data:
        f.write(item['text'] + "\n")

print(f"Transcript saved: {json_path} and {txt_path}")
