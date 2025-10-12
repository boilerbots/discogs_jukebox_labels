#!/usr/bin/env python3
"""
Flask web server for the Discogs Jukebox Label Maker.
"""

import asyncio
import re
from flask import Flask, render_template
from flask_socketio import SocketIO

from auto_id_core import (
    ShazamRecognizer,
    AudioRecorder,
    load_config,
    DiscogsAPI,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
SocketIO = SocketIO(app)

config = load_config("id_config.yaml")
if not config:
    raise RuntimeError("Could not load id_config.yaml")

discogs_api = DiscogsAPI(
    config.get("discogs_user_agent"),
    config.get("discogs_token"),
    config.get("discogs_country", "US"),
)

recorder = AudioRecorder(duration=10)
recognizer = ShazamRecognizer()

@app.route("/")
def index():
    return render_template("index.html")

@SocketIO.on("connect")
def handle_connect():
    print("Client connected")

@SocketIO.on("set_folder")
def handle_set_folder(folder_name):
    folder = discogs_api.get_or_create_folder(folder_name)
    if folder:
        SocketIO.emit("folder_set", {"folder_name": folder["name"], "folder_id": folder["id"]})
    else:
        SocketIO.emit("error", {"message": "Could not set folder."})

@SocketIO.on("identify")
def handle_identify(audio_data):
    audio_file = "temp_recording.wav"
    with open(audio_file, "wb") as f:
        f.write(audio_data)

    SocketIO.emit("status", {"message": "Identifying..."})
    result = asyncio.run(recognizer.recognize(audio_file))

    if result.get("status", {}).get("msg") == "Success":
        metadata = result["metadata"]["music"][0]
        raw_title = metadata["title"]
        # Remove text in parentheses and brackets
        clean_title = re.sub(r"\s*\(.*?\)", "", raw_title)
        clean_title = re.sub(r"\s*\[.*?\]", "", clean_title)
        title = clean_title.strip()
        artists = ", ".join([a["name"] for a in metadata["artists"]])
        SocketIO.emit("status", {"message": f"Searching for {title} by {artists}..."})
        releases = discogs_api.search_releases(title, artists)
        SocketIO.emit("search_results", {"releases": releases})
    else:
        SocketIO.emit("error", {"message": f"Could not identify song: {result.get('status', {}).get('msg')}"})

@SocketIO.on("add_release")
def handle_add_release(data):
    folder_id = data["folder_id"]
    release_id = data["release_id"]
    slot = data["slot"]

    if discogs_api.add_release_to_folder(folder_id, release_id, slot):
        SocketIO.emit("release_added", {"release_id": release_id})
    else:
        SocketIO.emit("error", {"message": "Could not add release."})

if __name__ == "__main__":
    SocketIO.run(app, debug=True, host="0.0.0.0", port=5000, ssl_context=('cert.pem', 'key.pem'))
