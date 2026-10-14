import argparse
import os
import json
from transcribr import Transcribr

parser = argparse.ArgumentParser(description="Transcribe YouTube video")

parser.add_argument("youtube_url_or_id", help="YouTube URL or Video ID")

args = parser.parse_args()

youtube_input = ' '.join(args.youtube_url_or_id)

# Extract video ID if URL
def extract_video_id(url_or_id):
    if "youtube.com" in url_or_id or "youtu.be" in url_or_id:
        if "v=" in url_or_id:
            return url_or_id.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url_or_id:
            return url_or_id.split("youtu.be/")[1].split("?")[0]
    return url_or_id.strip()

video_id = extract_video_id(youtube_input)

# Transcribe from YouTube
transcribr = Transcribr(model="base", device="cpu")
transcribr.transcribe(youtube_input)  # Assuming transcribr supports YouTube URLs

# Get transcript data
transcript_data = transcribr.get_transcript()  # Assuming this method exists

# Save JSON with timestamps
json_path = os.path.join(f"transcript_{video_id}.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(transcript_data, f, indent=4, ensure_ascii=False)

# Save TXT without timestamps
txt_path = os.path.join(f"transcript_{video_id}.txt")
with open(txt_path, "w", encoding="utf-8") as f:
    for item in transcript_data:
        f.write(item['text'] + "\n")

print(f"Transcript saved: {json_path} and {txt_path}")
