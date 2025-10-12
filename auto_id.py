#!/usr/bin/env python3
"""
Command-line interface for the Discogs Jukebox Label Maker.
"""

import argparse
import asyncio
import re
import sys

from auto_id_core import (
    ShazamRecognizer,
    AudioRecorder,
    load_config,
    DiscogsAPI,
)

def main():
    """Main function to run the vinyl single identifier from the command line."""
    parser = argparse.ArgumentParser(
        description="Identify vinyl singles and add them to a Discogs collection."
    )
    parser.add_argument(
        "--folder-name", help="The name of the Discogs collection folder to create."
    )
    args = parser.parse_args()

    config = load_config("id_config.yaml")
    if not config:
        return

    discogs_api = DiscogsAPI(
        config.get("discogs_user_agent"),
        config.get("discogs_token"),
        config.get("discogs_country", "US"),
    )
    if not discogs_api.username:
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

    folder = discogs_api.get_or_create_folder(folder_name)
    if not folder:
        return

    recognizer = ShazamRecognizer()
    audio_recorder = AudioRecorder(duration=10)
    slot_counter = 1

    while True:
        audio_file = audio_recorder.record()
        result = asyncio.run(recognizer.recognize(audio_file))

        if result.get("status", {}).get("msg") == "Success":
            metadata = result["metadata"]["music"][0]
            raw_title = metadata["title"]
            clean_title = re.sub(r"\s*\(.*?\)", "", raw_title)
            clean_title = re.sub(r"\s*\[.*?\]", "", clean_title)
            title = clean_title.strip()
            artists = ", ".join([a["name"] for a in metadata["artists"]])
            print(f"\n✓ Song Identified: {title} by {artists}")

            releases = discogs_api.search_releases(title, artists)
            if releases:
                print(f"Found {len(releases)} potential vinyl single(s):\n")
                for i, release in enumerate(releases[:10], 1):
                    print(f"{i}. {release['title']} ({release.get('country', 'N/A')} - {release.get('year', 'N/A')})")

                if not sys.stdout.isatty():
                    selected_release = releases[0]
                    discogs_api.add_release_to_folder(folder["id"], selected_release["id"], slot_counter)
                    slot_counter += 1
                else:
                    choice = input("Select a release by number to add (or 's' to skip): ")
                    if choice.lower() != "s":
                        try:
                            selected_release = releases[int(choice) - 1]
                            discogs_api.add_release_to_folder(folder["id"], selected_release["id"], slot_counter)
                            slot_counter += 1
                        except (ValueError, IndexError):
                            print("Invalid selection.")
            else:
                print("No matching vinyl singles found on Discogs.")
        else:
            print(f"Could not identify song: {result.get('status', {}).get('msg')}")

        if not sys.stdout.isatty():
            break
        if input("Identify another song? (y/n): ").lower() != "y":
            break

    print("Exiting.")


if __name__ == "__main__":
    main()
