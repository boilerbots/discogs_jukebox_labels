#!/usr/bin/env python3

import requests # Still needed for potential HTTP errors, but not direct API calls
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black
import time # For rate limiting, though discogs-client has some built-in handling
import discogs_client # Import the discogs-client library
import yaml # Import the yaml library for configuration file parsing
import os   # Import os for path checking

# --- Configuration (now loaded from YAML) ---
# DISCOGS_USER_TOKEN and DISCOGS_USERNAME will be read from discogs_labels_config.yaml

CONFIG_FILE = "discogs_labels_config.yaml"
DISCOGS_USER_TOKEN = None
DISCOGS_USERNAME = None
DISCOGS_COLLECTION_FOLDER = 0

OUTPUT_PDF_FILENAME = "Discogs_Jukebox_Labels.pdf"

# Jukebox Label Dimensions (adjust as needed)
# Typical jukebox labels are around 3-4 inches tall and 1-1.5 inches wide,
# often fitting 2-3 per row on an 8.5x11 sheet.
LABEL_WIDTH = 3.0 * inch # standard for 45 rpms
LABEL_HEIGHT = 1.0 * inch  # standard for 45 rpms
TITLE_WIDTH = 2.0 * inch
TITLE_HEIGHT = 0.20 * inch

# Margins and Spacing for PDF layout
PAGE_MARGIN_LEFT = 0.5 * inch
PAGE_MARGIN_TOP = 0.5 * inch
HORIZONTAL_SPACING = 0.125 * inch # Space between labels horizontally
VERTICAL_SPACING = 0.125 * inch   # Space between labels vertically

# Calculate labels per row and per page based on page size and label dimensions
# Standard letter page is 8.5 x 11 inches
LABELS_PER_ROW = int((letter[0] - 2 * PAGE_MARGIN_LEFT + HORIZONTAL_SPACING) / (LABEL_WIDTH + HORIZONTAL_SPACING))
LABELS_PER_COLUMN = int((letter[1] - 2 * PAGE_MARGIN_TOP + VERTICAL_SPACING) / (LABEL_HEIGHT + VERTICAL_SPACING))
LABELS_PER_PAGE = LABELS_PER_ROW * LABELS_PER_COLUMN

# --- PDF Label Generator ---

class JukeboxLabelPDFGenerator:
    """
    Generates a PDF document with jukebox-style labels.
    """
    def __init__(self, filename, page_size=letter):
        self.c = canvas.Canvas(filename, pagesize=page_size)
        self.page_width, self.page_height = page_size
        self.current_label_index = 0
        self.current_page_number = 1
        self.template = "/home/cmeyers/Downloads/labels/labels/Basic Redthick.jpg"
        print(f"Initializing PDF generator: {filename}")

    def _calculate_position(self, label_index_on_page):
        """
        Calculates the (x, y) coordinates for the top-left corner of a label
        on the current page.
        """
        col = label_index_on_page % LABELS_PER_ROW
        row = label_index_on_page // LABELS_PER_ROW

        x = PAGE_MARGIN_LEFT + col * (LABEL_WIDTH + HORIZONTAL_SPACING)
        y = self.page_height - PAGE_MARGIN_TOP - (row + 1) * (LABEL_HEIGHT + VERTICAL_SPACING) + VERTICAL_SPACING
        return x, y

    def add_label(self, release):
        """
        Adds a single jukebox label to the PDF using a discogs_client.Release object.
        Manages page breaks.
        """
        if self.current_label_index >= LABELS_PER_PAGE:
            self.c.showPage()
            self.current_label_index = 0
            self.current_page_number += 1
            print(f"Starting new page: {self.current_page_number}")

        x, y = self._calculate_position(self.current_label_index)

        # Background image
        # self.c.drawImage(self.template, x, y, width=LABEL_WIDTH, mask=None)

        # Draw the label border (optional, but good for visual debugging)
        self.c.rect(x, y, LABEL_WIDTH, LABEL_HEIGHT)
        self.c.rect(x + ((LABEL_WIDTH-TITLE_WIDTH)/2), y + (LABEL_HEIGHT/2) - (TITLE_HEIGHT/2), TITLE_WIDTH, TITLE_HEIGHT)

        # Extract information from the discogs_client.Release object
        artist = ", ".join([a.name for a in release.artists]) if release.artists else "Unknown Artist"
        # title = release.title if release.title else "Unknown Title"
        label_name = "Unknown Label"
        catalog_number = "N/A"
        #print(f"Artist: {artist}")
        #print(f"Tracks: {release.tracklist}")
        title_a = release.tracklist[0].title
        title_b = release.tracklist[1].title

        # discogs-client's Release object has a .labels attribute which is a list of Label objects
        if release.labels:
            primary_label = release.labels[0]
            label_name = primary_label.name if primary_label.name else label_name
            catalog_number = primary_label.catno if primary_label.catno else catalog_number

        # Content positioning within the label
        text_left_edge = x + 0.05 * inch # Small padding from left edge
        text_x = x + (LABEL_WIDTH/2) # Center
        text_width = LABEL_WIDTH - 0.1 * inch

        # Title A side
        font_size = 10
        self.c.setFont("Helvetica-Bold", font_size)
        # Wrap title if it's too long
        title_lines = self._wrap_text(title_a, "Helvetica-Bold", font_size, text_width)
        # Position title near the top of the label
        #title_y_start = y + LABEL_HEIGHT - 0.15 * inch
        title_y_start = y + (3*LABEL_HEIGHT/4) - font_size/2 # center
        for line in title_lines:
            self.c.drawCentredString(text_x, title_y_start, line)
            title_y_start -= 0.15 * inch # Move down for next line

        # Artist (below title)
        font_size = 8
        self.c.setFont("Helvetica", font_size)
        artist_lines = self._wrap_text(artist, "Helvetica", font_size, text_width)
        # artist_y_start = title_y_start - 0.1 * inch # Space below title
        artist_y_start = y + (LABEL_HEIGHT/2) - font_size/2 # center
        for line in artist_lines:
            self.c.drawCentredString(text_x, artist_y_start, line)
            artist_y_start -= 0.12 * inch # Move down for next line


        # Title B side
        font_size = 10
        self.c.setFont("Helvetica-Bold", font_size)
        # Wrap title if it's too long
        title_lines = self._wrap_text(title_b, "Helvetica-Bold", font_size, text_width)
        # Position title near the top of the label
        # title_y_start = y + (LABEL_HEIGHT/2) - 0.15 * inch
        title_y_start = y + (1*LABEL_HEIGHT/4) - font_size/2 # center
        for line in title_lines:
            self.c.drawCentredString(text_x, title_y_start, line)
            title_y_start -= 0.15 * inch # Move down for next line

        # Label and Catalog Number (at the bottom)
        self.c.setFont("Helvetica", 6)
        self.c.drawString(text_left_edge, y + 0.03 * inch, f"{label_name} {catalog_number}")
        #self.c.drawString(text_left_edge, y + 0.05 * inch, f"Cat#: {catalog_number}")

        self.current_label_index += 1

    def _wrap_text(self, text, font_name, font_size, max_width):
        """Helper to wrap text to fit within a given width."""
        self.c.setFont(font_name, font_size)
        lines = []
        words = text.split(' ')
        current_line = []
        for word in words:
            # Check if adding the next word exceeds max_width
            test_line = ' '.join(current_line + [word])
            if self.c.stringWidth(test_line) <= max_width:
                current_line.append(word)
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line)) # Add the last line
        return lines


    def save_pdf(self):
        """Saves the generated PDF document."""
        self.c.save()
        print(f"PDF saved as {OUTPUT_PDF_FILENAME}")

# --- Configuration Loading Function ---

def load_config(config_file_path):
    """
    Loads Discogs API token and username from a YAML file.
    """
    if not os.path.exists(config_file_path):
        print(f"ERROR: Configuration file '{config_file_path}' not found.")
        print("Please create a YAML file with the following structure:")
        print("discogs_user_token: YOUR_DISCOGS_USER_TOKEN")
        print("discogs_username: YOUR_DISCOGS_USERNAME")
        return None

    try:
        with open(config_file_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"ERROR: Could not parse YAML file '{config_file_path}': {e}")
        return None

# --- Main Script Execution ---

def main():
    global DISCOGS_USER_TOKEN, DISCOGS_USERNAME, DISCOGS_COLLECTION_FOLDER  # Declare global to modify them

    # Load configuration
    config = load_config(CONFIG_FILE)
    if not config:
        return

    DISCOGS_USER_TOKEN = config.get("discogs_user_token")
    DISCOGS_USERNAME = config.get("discogs_username")
    DISCOGS_COLLECTION_FOLDER = config.get("discogs_collection_folder")

    if not DISCOGS_USER_TOKEN or not DISCOGS_USERNAME:
        print("ERROR: 'discogs_user_token' or 'discogs_username' missing in the configuration file.")
        print("Please ensure your 'discogs_labels_config.yaml' file contains both keys.")
        return

    print("--- Starting Discogs Jukebox Label Generator ---")
    print(f"Fetching from folder: {DISCOGS_COLLECTION_FOLDER}")

    # Initialize the Discogs client using the discogs-client library
    # 'User-Agent' is automatically handled by discogs-client
    # 'request_limit_interval' and 'request_limit' can be adjusted if needed for rate limiting
    d = discogs_client.Client('DiscogsJukeboxLabelGenerator/1.0', user_token=DISCOGS_USER_TOKEN)
    pdf_generator = JukeboxLabelPDFGenerator(OUTPUT_PDF_FILENAME)

    try:
        # Get the user object
        user = d.identity()
        print(f"Authenticated as Discogs user: {user.username}")

        # Fetch collection releases directly using the discogs-client library
        # This handles pagination automatically and returns Release objects
        collection_releases = []
        print(f"Fetching collection for user: {user.username}...")
        for release_item in user.collection_folders[DISCOGS_COLLECTION_FOLDER].releases: # Folder 0 is "All"
            if len(release_item.release.tracklist) > 2:
                print(f"Skip: {release_item.release.title} by {', '.join([a.name for a in release_item.release.artists])}")
                continue
            collection_releases.append(release_item.release) # Get the actual Release object from the CollectionRelease object
            print(f"Adding: {release_item.release.title} by {', '.join([a.name for a in release_item.release.artists])}")
            # Small delay to be extra cautious with rate limits, although discogs-client manages it
            time.sleep(0.1)

        if not collection_releases:
            print("No releases found in your collection. Exiting.")
            return

        print(f"\nGenerating labels for {len(collection_releases)} releases...")
        for i, release in enumerate(collection_releases):
            # Pass the discogs_client.Release object directly to add_label
            pdf_generator.add_label(release)
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1} labels...")

        pdf_generator.save_pdf()
        print("--- Discogs Jukebox Label Generator Finished ---")

    except discogs_client.exceptions.DiscogsAPIError as e:
        print(f"Discogs API Error: {e}")
        print("Please check your Discogs User Token and Username in the configuration file.")
    except requests.exceptions.RequestException as e:
        print(f"Network or request error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")

if __name__ == "__main__":
    main()

