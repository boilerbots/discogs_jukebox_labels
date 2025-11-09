#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import yaml
import os
import discogs_labels
import sys
from threading import Thread

CONFIG_FILE = "discogs_labels_config.yaml"

class DiscogsLabelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Discogs Jukebox Label Generator")

        self.token_label = ttk.Label(root, text="Discogs User Token:")
        self.token_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.token_entry = ttk.Entry(root, width=50)
        self.token_entry.grid(row=0, column=1, padx=10, pady=5)

        self.folder_label = ttk.Label(root, text="Collection Folder:")
        self.folder_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.folder_entry = ttk.Entry(root, width=50)
        self.folder_entry.grid(row=1, column=1, padx=10, pady=5)

        self.generate_button = ttk.Button(root, text="Generate Labels", command=self.start_generation_thread)
        self.generate_button.grid(row=2, column=0, columnspan=2, pady=10)

        self.status_text = tk.Text(root, height=15, width=80)
        self.status_text.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        
        # Redirect stdout to the text widget
        sys.stdout = self.TextRedirector(self.status_text)
        sys.stderr = self.TextRedirector(self.status_text)


        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.config = yaml.safe_load(f)
                if self.config:
                    self.token_entry.insert(0, self.config.get("discogs_user_token", ""))
                    self.folder_entry.insert(0, self.config.get("discogs_collection_folder", ""))

    def save_config(self):
        self.config["discogs_user_token"] = self.token_entry.get()
        self.config["discogs_collection_folder"] = self.folder_entry.get()
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f)

    def generate_labels(self):
        self.save_config()
        self.status_text.delete(1.0, tk.END)
        print("Starting label generation...")
        self.root.update_idletasks()

        try:
            discogs_labels.main()
            print("\nLabel generation finished!")
        except Exception as e:
            print(f"\nAn error occurred: {e}")
        finally:
            self.generate_button.config(state=tk.NORMAL)


    def start_generation_thread(self):
        self.generate_button.config(state=tk.DISABLED)
        self.generation_thread = Thread(target=self.generate_labels)
        self.generation_thread.start()

    class TextRedirector(object):
        def __init__(self, widget):
            self.widget = widget

        def write(self, str):
            self.widget.insert(tk.END, str)
            self.widget.see(tk.END)
        
        def flush(self):
            pass

def main():
    root = tk.Tk()
    app = DiscogsLabelApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
