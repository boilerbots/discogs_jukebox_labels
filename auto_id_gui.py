#!/usr/bin/env python3
"""
GUI for the Discogs Jukebox Label Maker.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import os

from auto_id_core import (
    ACRCloudRecognizer,
    AudioRecorder,
    load_config,
    DiscogsAPI,
)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Discogs Jukebox Label Maker")
        self.geometry("800x600")

        self.config = load_config("id_config.yaml")
        if not self.config:
            messagebox.showerror("Error", "Could not load id_config.yaml.")
            self.destroy()
            return

        self.discogs_api = DiscogsAPI(
            self.config.get("discogs_user_agent"),
            self.config.get("discogs_token"),
            self.config.get("discogs_country", "US"),
        )
        if not self.discogs_api.username:
            messagebox.showerror("Error", "Could not authenticate with Discogs.")
            self.destroy()
            return

        self.recorder = AudioRecorder(duration=10)
        self.recognizer = ACRCloudRecognizer(
            self.config.get("acrcloud_access_key"),
            self.config.get("acrcloud_access_secret"),
            self.config.get("acrcloud_host"),
        )

        self.folder = None
        self.slot_counter = 1
        self.slot_counter_var = tk.StringVar(value=str(self.slot_counter))

        self.create_widgets()

    def create_widgets(self):
        folder_frame = ttk.Frame(self)
        folder_frame.pack(pady=10)
        ttk.Label(folder_frame, text="Discogs Folder Name:").pack(side=tk.LEFT, padx=5)
        self.folder_name_entry = ttk.Entry(folder_frame, width=40)
        self.folder_name_entry.pack(side=tk.LEFT, padx=5)
        self.set_folder_button = ttk.Button(
            folder_frame, text="Set Folder", command=self.set_folder
        )
        self.set_folder_button.pack(side=tk.LEFT, padx=5)

        slot_counter_frame = ttk.Frame(self)
        slot_counter_frame.pack(pady=5)
        ttk.Label(slot_counter_frame, text="Slot Counter:").pack(side=tk.LEFT, padx=5)
        ttk.Button(slot_counter_frame, text="-", command=self.decrement_slot, width=2).pack(side=tk.LEFT)
        ttk.Label(slot_counter_frame, textvariable=self.slot_counter_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(slot_counter_frame, text="+", command=self.increment_slot, width=2).pack(side=tk.LEFT)

        self.status_label = ttk.Label(self, text="Ready")
        self.status_label.pack(pady=5)

        self.start_button = ttk.Button(
            self, text="Start Identification", command=self.start_identification_thread, state=tk.DISABLED
        )
        self.start_button.pack(pady=10)

        results_frame = ttk.Frame(self)
        results_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        ttk.Label(results_frame, text="Search Results:").pack()
        self.results_listbox = tk.Listbox(results_frame, width=100, height=20)
        self.results_listbox.pack(fill=tk.BOTH, expand=True, padx=10)

        self.add_button = ttk.Button(
            self, text="Add Selected to Folder", command=self.add_selected_release, state=tk.DISABLED
        )
        self.add_button.pack(pady=10)

    def set_folder(self):
        folder_name = self.folder_name_entry.get()
        if not folder_name:
            messagebox.showerror("Error", "Please enter a folder name.")
            return

        self.folder = self.discogs_api.get_or_create_folder(folder_name)
        if self.folder:
            self.status_label.config(text=f"Using folder '{folder_name}'.")
            self.start_button.config(state=tk.NORMAL)
            self.set_folder_button.config(state=tk.DISABLED)
            self.folder_name_entry.config(state=tk.DISABLED)
        else:
            messagebox.showerror("Error", "Could not set folder.")

    def increment_slot(self):
        self.slot_counter += 1
        self.slot_counter_var.set(str(self.slot_counter))

    def decrement_slot(self):
        if self.slot_counter > 1:
            self.slot_counter -= 1
            self.slot_counter_var.set(str(self.slot_counter))

    def start_identification_thread(self):
        self.start_button.config(state=tk.DISABLED)
        self.add_button.config(state=tk.DISABLED)
        self.results_listbox.delete(0, tk.END)
        self.status_label.config(text="Identifying...")
        threading.Thread(target=self.identify_and_display, daemon=True).start()

    def identify_and_display(self):
        audio_file = self.recorder.record()
        result = self.recognizer.recognize(audio_file)
        os.remove(audio_file)

        if result.get("status", {}).get("msg") == "Success":
            metadata = result["metadata"]["music"][0]
            raw_title = metadata["title"]
            clean_title = re.sub(r"\s*\(.*?\)", "", raw_title)
            clean_title = re.sub(r"\s*\[.*?\]", "", clean_title)
            title = clean_title.strip()
            artists = ", ".join([a["name"] for a in metadata["artists"]])
            self.releases = self.discogs_api.search_releases(title, artists)
            self.after(0, self.update_ui_after_identification, f"Found {len(self.releases)} releases for {title} by {artists}")
        else:
            self.after(0, self.update_ui_after_identification, f"Could not identify song: {result.get('status', {}).get('msg')}")

    def update_ui_after_identification(self, status_text):
        self.status_label.config(text=status_text)
        if self.releases:
            for release in self.releases:
                self.results_listbox.insert(tk.END, f"{release['title']} ({release.get('country', 'N/A')} - {release.get('year', 'N/A')})")
            self.add_button.config(state=tk.NORMAL)
        else:
            self.results_listbox.insert(tk.END, "No results found.")
        self.start_button.config(state=tk.NORMAL)

    def add_selected_release(self):
        selected_index = self.results_listbox.curselection()
        if not selected_index:
            messagebox.showerror("Error", "Please select a release to add.")
            return

        selected_release = self.releases[selected_index[0]]
        if self.discogs_api.add_release_to_folder(self.folder["id"], selected_release["id"], self.slot_counter):
            self.status_label.config(
                text=f"Added '{selected_release['title']}' to folder. Slot: {self.slot_counter}"
            )
            self.increment_slot()
            self.results_listbox.delete(selected_index)
        else:
            messagebox.showerror("Error", "Could not add release.")

if __name__ == "__main__":
    app = App()
    app.mainloop()