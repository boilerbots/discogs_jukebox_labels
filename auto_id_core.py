#!/usr/bin/env python3
"""
Core logic for recording a vinyl single, identifying it using ACRCloud,
searching for it on Discogs, and adding it to a collection folder.
"""

import base64
import hashlib
import hmac
import os
import time
import wave

import sounddevice as sd
import numpy as np
import requests
import yaml

CONFIG_FILE = "id_config.yaml"


import asyncio
from shazamio import Shazam

CONFIG_FILE = "id_config.yaml"


class ShazamRecognizer:
    """Recognizes audio using the Shazam API via shazamio."""

    async def recognize(self, audio_file):
        """Recognize audio using Shazam API"""
        try:
            shazam = Shazam()
            track = await shazam.recognize_song(audio_file)
            if track and track.get('track'):
                track_info = track['track']
                return {
                    "status": {"msg": "Success"},
                    "metadata": {
                        "music": [
                            {
                                "title": track_info.get('title', 'Unknown Title'),
                                "artists": [{"name": track_info.get('subtitle', 'Unknown Artist')}],
                            }
                        ]
                    },
                }
            else:
                return {"status": {"msg": "No match found."}}
        except Exception as e:
            print(f"Error during Shazam recognition: {e}")
            return {"status": {"msg": f"Recognition failed: {e}"}}


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self, duration=10, sample_rate=44100, channels=1):
        self.duration = duration
        self.sample_rate = sample_rate
        self.channels = channels

    def record(self, output_file="temp_recording.wav"):
        """Record audio from microphone"""
        print(f"Recording for {self.duration} seconds...")
        recording = sd.rec(int(self.duration * self.sample_rate), samplerate=self.sample_rate, channels=self.channels, dtype='int16')
        sd.wait()
        print("Recording complete!")

        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())

        return output_file


class DiscogsAPI:
    """A wrapper for the Discogs API using requests."""
    def __init__(self, user_agent, token, country="US"):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": user_agent,
            "Authorization": f"Discogs token={token}",
        }
        self.username = self._get_username()
        self.slot_field_id = self._get_slot_field_id()
        self.country = country

    def _get_username(self):
        """Get the username of the authenticated user."""
        try:
            response = requests.get(f"{self.base_url}/oauth/identity", headers=self.headers)
            response.raise_for_status()
            return response.json()["username"]
        except requests.RequestException as e:
            print(f"Error getting username: {e}")
            return None

    def _get_slot_field_id(self):
        """Get the ID of the 'Slot' custom field."""
        if not self.username:
            return None
        try:
            response = requests.get(f"{self.base_url}/users/{self.username}/collection/fields", headers=self.headers)
            response.raise_for_status()
            for field in response.json()["fields"]:
                if field["name"] == "Slot":
                    return field["id"]
            return None
        except requests.RequestException as e:
            print(f"Error getting custom fields: {e}")
            return None

    def get_or_create_folder(self, folder_name):
        """Get an existing folder by name or create it if it doesn't exist."""
        try:
            response = requests.get(f"{self.base_url}/users/{self.username}/collection/folders", headers=self.headers)
            response.raise_for_status()
            for folder in response.json()["folders"]:
                if folder["name"] == folder_name:
                    print(f"Found existing folder: '{folder_name}'")
                    return folder
            
            response = requests.post(f"{self.base_url}/users/{self.username}/collection/folders", headers=self.headers, json={"name": folder_name})
            response.raise_for_status()
            print(f"Successfully created folder: '{folder_name}'")
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting or creating folder: {e}")
            return None

    def search_releases(self, title, artist):
        """Search for vinyl singles on Discogs."""
        params = {
            "release_title": title,
            "artist": artist,
            "type": "release",
            "format": "Vinyl",
            #"country": self.country,
        }
        print(f"Searching for {params}")
        try:
            response = requests.get(f"{self.base_url}/database/search", headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            all_results = data.get('results', [])
            results = []

            for r in all_results:
                formats = r.get("format", [])
                is_single = all(f in str(formats).lower() for f in ["single", '7"', '45'])
                if is_single and r.get('country', '') == self.country:
                    results.append(r)

            if not results:
                print(f"No matches, just send everything")
                for r in all_results:
                    results.append(r)

            #if not results:
            #    print(f"No results found for country '{self.country}', searching all countries...")
            #    del params["country"]
            #    response = requests.get(f"{self.base_url}/database/search", headers=self.headers, params=params)
            #    response.raise_for_status()
            #    results = [
            #        r for r in response.json()["results"]
            #        if all(f in str(r.get("format", [])).lower() for f in ["single", '7"'])
            #    ]
            return results
        except requests.RequestException as e:
            print(f"Error searching releases: {e}")
            return []

    def add_release_to_folder(self, folder_id, release_id, slot):
        """Add a release to a folder and set the 'Slot' custom field."""
        try:
            url = f"{self.base_url}/users/{self.username}/collection/folders/{folder_id}/releases/{release_id}"
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            instance_id = response.json()["instance_id"]
            
            if self.slot_field_id:
                field_url = f"{url}/instances/{instance_id}/fields/{self.slot_field_id}"
                requests.post(field_url, headers=self.headers, json={"value": str(slot)}).raise_for_status()
            
            print(f"Added release to folder. Slot: {slot}")
            return True
        except requests.RequestException as e:
            print(f"Error adding release to folder: {e}")
            return False


def load_config(config_file_path):
    """Loads configuration from a YAML file."""
    if not os.path.exists(config_file_path):
        print(f"ERROR: Configuration file '{config_file_path}' not found.")
        return None
    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: Could not parse YAML file '{config_file_path}': {e}")
        return None
