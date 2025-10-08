#!/usr/bin/env python3
"""
Records a vinyl single, identifies it using ACRCloud,
searches for it on Discogs, and adds it to a collection folder.
"""

import argparse
import base64
import hashlib
import hmac
import os
import sys
import time
import wave

import discogs_client
import pyaudio
import requests
import yaml

CONFIG_FILE = "id_config.yaml"


class ACRCloudRecognizer:
    """Recognizes audio using the ACRCloud API."""

    def __init__(self, access_key, access_secret, host):
        self.access_key = access_key
        self.access_secret = access_secret
        self.host = host

    def recognize(self, audio_file):
        """Recognize audio using ACRCloud API"""
        http_method = "POST"
        http_uri = "/v1/identify"
        data_type = "audio"
        signature_version = "1"
        timestamp = str(int(time.time()))

        # Create signature
        string_to_sign = (
            f"{http_method}\n{http_uri}\n{self.access_key}\n"
            f"{data_type}\n{signature_version}\n{timestamp}"
        )
        sign = base64.b64encode(
            hmac.new(
                self.access_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        # Prepare the request
        with open(audio_file, "rb") as f:
            sample_bytes = f.read()

        files = {"sample": (audio_file, sample_bytes)}
        data = {
            "access_key": self.access_key,
            "sample_bytes": len(sample_bytes),
            "timestamp": timestamp,
            "signature": sign,
            "data_type": data_type,
            "signature_version": signature_version,
        }

        url = f"https://{self.host}{http_uri}"
        try:
            response = requests.post(url, files=files, data=data, timeout=10)
            return response.json()
        except requests.Timeout:
            return {"status": {"msg": "Request timed out"}}
        except requests.RequestException as e:
            return {"status": {"msg": f"Request failed: {e}"}}


class AudioRecorder:
    """Records audio from the microphone."""

    def __init__(self, duration=10, sample_rate=44100, channels=1):
        self.duration = duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk = 1024

    def record(self, output_file="temp_recording.wav"):
        """Record audio from microphone"""
        p = pyaudio.PyAudio()

        print(f"Recording for {self.duration} seconds...")

        stream = p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk,
        )

        frames = []
        for _ in range(0, int(self.sample_rate / self.chunk * self.duration)):
            data = stream.read(self.chunk)
            frames.append(data)

        print("Recording complete!")

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save to WAV file
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))

        return output_file


def load_config(config_file_path):
    """
    Loads configuration from a YAML file.
    """
    if not os.path.exists(config_file_path):
        print(f"ERROR: Configuration file '{config_file_path}' not found.")
        print("Please create a YAML file with the following structure:")
        print("acrcloud_access_key: YOUR_ACRCLOUD_ACCESS_KEY")
        print("acrcloud_access_secret: YOUR_ACRCLOUD_ACCESS_SECRET")
        print("acrcloud_host: YOUR_ACRCLOUD_HOST")
        print("discogs_user_agent: YOUR_DISCOGS_USER_AGENT")
        print("discogs_token: YOUR_DISCOGS_TOKEN")
        return None

    try:
        with open(config_file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"ERROR: Could not parse YAML file '{config_file_path}': {e}")
        return None


def main():
    """Main function to run the vinyl single identifier."""
    parser = argparse.ArgumentParser(
        description="Identify vinyl singles and add them to a Discogs collection."
    )
    parser.add_argument(
        "--folder-name", help="The name of the Discogs collection folder to create."
    )
    args = parser.parse_args()

    config = load_config(CONFIG_FILE)
    if not config:
        return

    acrcloud_access_key = config.get("acrcloud_access_key")
    acrcloud_access_secret = config.get("acrcloud_access_secret")
    acrcloud_host = config.get("acrcloud_host")
    discogs_user_agent = config.get("discogs_user_agent")
    discogs_token = config.get("discogs_token")

    if not all(
        [
            acrcloud_access_key,
            acrcloud_access_secret,
            acrcloud_host,
            discogs_user_agent,
            discogs_token,
        ]
    ):
        print("ERROR: One or more configuration keys are missing from id_config.yaml.")
        return

    recorder = AudioRecorder(duration=10)
    recognizer = ACRCloudRecognizer(
        acrcloud_access_key, acrcloud_access_secret, acrcloud_host
    )

    try:
        discogs_client_instance = discogs_client.Client(
            discogs_user_agent, user_token=discogs_token
        )
        user = discogs_client_instance.identity()
        print(f"Authenticated as Discogs user: {user.username}")
    except discogs_client.exceptions.DiscogsAPIError as e:
        print(f"Failed to authenticate with Discogs: {e}")
        return

    if args.folder_name:
        folder_name = args.folder_name
    elif not sys.stdout.isatty():
        print("Running in non-interactive mode. Please provide a folder name with --folder-name.")
        return
    else:
        folder_name = input("Enter the name for the new Discogs collection folder: ")
        if not folder_name:
            print("Folder name cannot be empty. Exiting.")
            return

        confirm_create = input(
            f"Are you sure you want to create a new folder named '{folder_name}'? (y/n): "
        )
        if confirm_create.lower() != "y":
            print("Folder creation cancelled. Exiting.")
            return

    try:
        new_folder = user.collection_folders.create(folder_name)
        print(f"Successfully created folder: '{folder_name}'")
    except discogs_client.exceptions.DiscogsAPIError as e:
        print(f"Failed to create folder: {e}")
        return

    slot_counter = 1
    while True:
        print("\n=== Vinyl Single Identifier ===")
        audio_file = recorder.record()

        try:
            print("\nIdentifying song...")
            result = recognizer.recognize(audio_file)

            if result.get("status", {}).get("msg") == "Success":
                metadata = result["metadata"]["music"][0]
                title = metadata["title"]
                artists = ", ".join([artist["name"] for artist in metadata["artists"]])

                print(f"\n✓ Song Identified: {title} by {artists}")

                print("\nSearching Discogs for vinyl singles...")
                search_results = discogs_client_instance.search(
                    release_title=title,
                    artist=artists,
                    type="release",
                    format="Vinyl",
                )

                singles = [
                    res
                    for res in search_results
                    if any(fmt in str(res.formats).lower() for fmt in ["single", '7"'])
                ]

                if singles:
                    print(f"Found {len(singles)} potential vinyl single(s):\n")
                    for i, single in enumerate(singles[:20], 1):  # Show top 20
                        print(f"{i}. {single.title} ({', '.join(single.country_and_year)})")

                    if not sys.stdout.isatty():
                        # In non-interactive mode, just add the first result
                        selected_release = singles[0]
                        try:
                            added_item = new_folder.add_release(selected_release.id)
                            print(f"Added '{selected_release.title}' to folder.")
                            added_item.set_field("Slot", str(slot_counter))
                            print(f"Set 'Slot' to {slot_counter}.")
                            slot_counter += 1
                        except discogs_client.exceptions.DiscogsAPIError as e:
                            print(f"Error adding release or setting field: {e}")
                    else:
                        while True:
                            choice = input(
                                "Select a release by number to add (or 's' to skip): "
                            )
                            if choice.lower() == "s":
                                break
                            try:
                                selected_index = int(choice) - 1
                                if 0 <= selected_index < len(singles):
                                    selected_release = singles[selected_index]

                                    confirm_add = input(
                                        f"Add '{selected_release.title}' to '{folder_name}'? (y/n): "
                                    )
                                    if confirm_add.lower() == "y":
                                        try:
                                            added_item = new_folder.add_release(
                                                selected_release.id
                                            )
                                            print(
                                                f"Added '{selected_release.title}' to folder."
                                            )

                                            added_item.set_field("Slot", str(slot_counter))
                                            print(f"Set 'Slot' to {slot_counter}.")
                                            slot_counter += 1

                                        except discogs_client.exceptions.DiscogsAPIError as e:
                                            print(
                                                f"Error adding release or setting field: {e}"
                                            )
                                    break
                                print("Invalid number. Please try again.")
                            except ValueError:
                                print("Invalid input. Please enter a number or 's'.")
                else:
                    print("No matching vinyl singles found on Discogs.")
            else:
                print(
                    f"Could not identify song: {result.get('status', {}).get('msg')}"
                )

        finally:
            if os.path.exists(audio_file):
                os.remove(audio_file)
                print(f"Cleaned up temporary file: {audio_file}")

        if not sys.stdout.isatty():
            break

        if input("Identify another song? (y/n): ").lower() != "y":
            break

    print("Exiting.")


if __name__ == "__main__":
    main()
