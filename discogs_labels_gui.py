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

        self.template_label = ttk.Label(root, text="Label Template:")
        self.template_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.template_entry = ttk.Entry(root, width=50)
        self.template_entry.grid(row=2, column=1, padx=10, pady=5)

        self.color_label = ttk.Label(root, text="Label Color:")
        self.color_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.color_entry = ttk.Entry(root, width=50)
        self.color_entry.grid(row=3, column=1, padx=10, pady=5)

        self.fill_color_label = ttk.Label(root, text="Fill Color:")
        self.fill_color_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.fill_color_entry = ttk.Entry(root, width=50)
        self.fill_color_entry.grid(row=4, column=1, padx=10, pady=5)

        self.opacity_label = ttk.Label(root, text="Fill Opacity:")
        self.opacity_label.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.opacity_entry = ttk.Entry(root, width=50)
        self.opacity_entry.grid(row=5, column=1, padx=10, pady=5)

        self.sanitize = tk.BooleanVar()
        self.check_button = ttk.Checkbutton(root, text="Sanitize Artist Names", variable=self.sanitize)
        self.check_button.grid(row=6, column=0, columnspan=1, pady=10)
        self.generate_button = ttk.Button(root, text="Generate Labels", command=self.start_generation_thread)
        self.generate_button.grid(row=6, column=1, columnspan=1, pady=10)

        self.status_text = tk.Text(root, height=15, width=80)
        self.status_text.grid(row=7, column=0, columnspan=2, padx=10, pady=10)
        
        # Redirect stdout to the text widget
        sys.stdout = self.TextRedirector(self.status_text)
        sys.stderr = self.TextRedirector(self.status_text)


        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                self.config = yaml.safe_load(f)
        
        if not hasattr(self, 'config') or self.config is None:
            self.config = {}

        self.token_entry.insert(0, self.config.get("discogs_user_token", ""))
        self.folder_entry.insert(0, self.config.get("discogs_collection_folder", ""))
        self.template_entry.insert(0, self.config.get("label_template", "label001.svg"))
        self.color_entry.insert(0, self.config.get("label_color", "#FF0000"))
        self.fill_color_entry.insert(0, self.config.get("label_color_fill", "#FF0000"))
        self.opacity_entry.insert(0, self.config.get("label_color_fill_opacity", "0.25"))
        self.sanitize.set(self.config.get("clean_artist_strings", True))

    def save_config(self):
        self.config["discogs_user_token"] = self.token_entry.get()
        self.config["discogs_collection_folder"] = self.folder_entry.get()
        self.config["label_template"] = self.template_entry.get()
        self.config["label_color"] = self.color_entry.get()
        self.config["label_color_fill"] = self.fill_color_entry.get()
        self.config["clean_artist_strings"] = self.sanitize.get()
        try:
            opacity = float(self.opacity_entry.get())
        except ValueError:
            opacity = 0.25 # default back
        self.config["label_color_fill_opacity"] = opacity
        
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(self.config, f)

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
