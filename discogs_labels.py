#!/usr/bin/env python3

import requests  # Still needed for potential HTTP errors, but not direct API calls
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Path, Line
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg
import time  # For rate limiting, though discogs-client has some built-in handling
import discogs_client  # Import the discogs-client library
import yaml  # Import the yaml library for configuration file parsing
import os  # Import os for path checking
import xml.etree.ElementTree as etree
import re

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), relative_path))

# --- Configuration (now loaded from YAML) ---
# DISCOGS_USER_TOKEN will be read from discogs_labels_config.yaml

CONFIG_FILE = "discogs_labels_config.yaml"
DISCOGS_USER_TOKEN = None
DISCOGS_COLLECTION_FOLDER = 0

OUTPUT_PDF_FILENAME = "Discogs_Jukebox_Labels.pdf"

# Jukebox Label Dimensions (adjust as needed)
# Typical jukebox labels are around 3-4 inches tall and 1-1.5 inches wide,
# often fitting 2-3 per row on an 8.5x11 sheet.
LABEL_WIDTH = 3.0 * inch  # standard for 45 rpms
LABEL_HEIGHT = 1.0 * inch  # standard for 45 rpms
TITLE_WIDTH = 2.0 * inch
TITLE_HEIGHT = 0.20 * inch

# Margins and Spacing for PDF layout
PAGE_MARGIN_LEFT = 0.5 * inch
PAGE_MARGIN_TOP = 0.5 * inch
HORIZONTAL_SPACING = 0.005 * inch  # Space between labels horizontally
VERTICAL_SPACING = 0.005 * inch  # Space between labels vertically

# Calculate labels per row and per page based on page size and label dimensions
# Standard letter page is 8.5 x 11 inches
LABELS_PER_ROW = int(
    (letter[0] - PAGE_MARGIN_LEFT + HORIZONTAL_SPACING)
    / (LABEL_WIDTH + HORIZONTAL_SPACING)
)
LABELS_PER_COLUMN = int(
    (letter[1] - PAGE_MARGIN_TOP + VERTICAL_SPACING)
    / (LABEL_HEIGHT + VERTICAL_SPACING)
)
LABELS_PER_PAGE = LABELS_PER_ROW * LABELS_PER_COLUMN

# --- PDF Label Generator ---


class JukeboxLabelPDFGenerator:
    """
    Generates a PDF document with jukebox-style labels.
    """

    def __init__(self, filename, config, page_size=letter):
        original_label_template = config.get("label_template", "label001.svg")
        self.label_template = resource_path(original_label_template)
        self.label_color = config.get("label_color", "#FF0000")  # Color in RGB
        self.label_color_fill = config.get("label_color_fill", "#FF0000")  # Color in RGB
        self.label_color_fill_opacity = config.get("label_color_fill_opacity", 0.25)
        self.label_show_label = config.get("label_show_label", True)
        self.label_show_catno = config.get("label_show_catno", True)
        self.label_font_title = config.get("label_font_title", "Helvetica-Bold")
        self.label_font_artist = config.get("label_font_artist", "Helvetica")
        self.label_font_other = config.get("label_font_other", "Helvetica")
        print(f"Initializing PDF generator: {filename}")
        self.c = canvas.Canvas(filename, pagesize=page_size)
        self.page_width, self.page_height = page_size
        self.current_label_index = 0
        self.current_page_number = 1
        self.change_stroke_color(self.label_template, "tmp_label.svg")

    def _calculate_position(self, label_index_on_page):
        """
        Calculates the (x, y) coordinates for the top-left corner of a label
        on the current page.
        """
        col = label_index_on_page % LABELS_PER_ROW
        row = label_index_on_page // LABELS_PER_ROW

        x = PAGE_MARGIN_LEFT + col * (LABEL_WIDTH + HORIZONTAL_SPACING)
        y = (
            self.page_height
            - PAGE_MARGIN_TOP
            - (row + 1) * (LABEL_HEIGHT + VERTICAL_SPACING)
            + VERTICAL_SPACING
        )
        return x, y

    def change_stroke_color(self, in_name, out_name):
        tree = etree.parse(in_name)
        root = tree.getroot()
        new_stroke_color = self.label_color
        new_fill_color = self.label_color_fill
        new_opacity = self.label_color_fill_opacity
        for element in root.iter():
            # Check if the element has a 'stroke' attribute
            #if "stroke" in element.attrib:
            #    element.set("stroke", new_stroke_color)
            # Check for 'style' attribute which might contain stroke property
            if "style" in element.attrib:
                style_attr = element.get("style")
                updated_style = []
                for prop in style_attr.split(";"):
                    prop = prop.strip()
                    if prop.startswith("stroke:"):
                        updated_style.append(f"stroke:{new_stroke_color}")
                    #elif prop.startswith("fill:") and not "none" in prop:
                    #elif prop.startswith("fill:") and re.search(r"rect", element.tag):
                    elif prop.startswith("fill:"):
                        updated_style.append(f"fill:{new_fill_color}")
                        new_fill_color = "#FFFFFF"
                    elif prop.startswith("fill-opacity:"):
                        updated_style.append(f"fill-opacity:{new_opacity}")
                        new_opacity = 1.0
                    else:
                        updated_style.append(prop)
                element.set("style", ";".join(updated_style))
        tree.write(out_name)

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
        # self.c.drawImage(self.label_template, x, y, LABEL_WIDTH, LABEL_HEIGHT, preserveAspectRatio=False)
        # drawing = svg2rlg("label001.svg")
        drawing = svg2rlg("tmp_label.svg")
        renderPDF.draw(drawing, self.c, x, y)

        # Draw the label border (optional, but good for visual debugging)
        # self.c.rect(x, y, LABEL_WIDTH, LABEL_HEIGHT)
        # self.c.rect(x + ((LABEL_WIDTH-TITLE_WIDTH)/2), y + (LABEL_HEIGHT/2) - (TITLE_HEIGHT/2), TITLE_WIDTH, TITLE_HEIGHT)

        # Extract information from the discogs_client.Release object
        artist = (
            ", ".join([a.name for a in release.artists])
            if release.artists
            else "Unknown Artist"
        )
        # title = release.title if release.title else "Unknown Title"
        label_name = "Unknown Label"
        catalog_number = "N/A"
        print(f"Artist: {artist}")
        title_a = ""
        title_b = ""
        if len(release.tracklist) == 2:
            title_a = release.tracklist[0].title
            title_b = release.tracklist[1].title
        else:
            for track in release.tracklist:
                print(f"  Track {track.position} : {track.title}")
                if len(track.position) == 0:  # because of [r1589174]
                    continue
                # Some singles label second side "AA" if it had a hit song
                if (track.position[0] == "A") and not (track.position == "AA"):
                    if len(title_a) > 0:
                        title_a += " / "
                    title_a += track.title
                if (track.position[0] == "B") or (track.position == "AA"):
                    if len(title_b) > 0:
                        title_b += " / "
                    title_b += track.title

        # discogs-client's Release object has a .labels attribute which is a list of Label objects
        # print(f"labels: {dir(release)}")
        if release.labels:
            primary_label = release.labels[0]
            label_name = primary_label.name if primary_label.name else label_name
            catalog_number = primary_label.fetch("catno")  # have to ask for this

        # Content positioning within the label
        text_left_edge = x + 0.05 * inch  # Small padding from left edge
        text_x = x + (LABEL_WIDTH / 2)  # Center
        text_width = LABEL_WIDTH - 0.1 * inch

        # Title A side
        font_size = 12
        font_size = self._fit_text(
            title_a, self.label_font_title, font_size, text_width
        )
        # Wrap title if it's too long
        title_lines = self._wrap_text(
            title_a, self.label_font_title, font_size, text_width
        )
        # Position title near the top of the label
        # title_y_start = y + LABEL_HEIGHT - 0.15 * inch
        title_y_start = y + (3 * LABEL_HEIGHT / 4)  # - font_size/2 # center
        self.c.setFont(self.label_font_title, font_size)
        for line in title_lines:
            self.c.drawCentredString(text_x, title_y_start, line)
            title_y_start -= 0.15 * inch  # Move down for next line

        # Artist (below title)
        font_size = 10
        self.c.setFont(self.label_font_artist, font_size)
        artist_lines = self._wrap_text(
            artist, self.label_font_artist, font_size, text_width
        )
        # artist_y_start = title_y_start - 0.1 * inch # Space below title
        artist_y_start = y + (LABEL_HEIGHT / 2) - font_size / 3  # center
        for line in artist_lines:
            self.c.drawCentredString(text_x, artist_y_start, line)
            artist_y_start -= 0.12 * inch  # Move down for next line

        # Title B side
        font_size = 12
        font_size = self._fit_text(
            title_b, self.label_font_title, font_size, text_width
        )
        # Wrap title if it's too long
        title_lines = self._wrap_text(
            title_b, self.label_font_title, font_size, text_width
        )
        # Position title near the top of the label
        # title_y_start = y + (LABEL_HEIGHT/2) - 0.15 * inch
        title_y_start = y + (1 * LABEL_HEIGHT / 4) - font_size * 2 / 3  # center
        self.c.setFont(self.label_font_title, font_size)
        for line in title_lines:
            self.c.drawCentredString(text_x, title_y_start, line)
            title_y_start -= 0.15 * inch  # Move down for next line

        # Label and Catalog Number (at the bottom)
        self.c.setFont(self.label_font_other, 6)
        if self.label_show_label:
            self.c.drawString(text_left_edge, y + 0.06 * inch, f"{label_name}")
        if self.label_show_catno:
            self.c.drawRightString(
                x + LABEL_WIDTH - 0.06 * inch, y + 0.06 * inch, f"{catalog_number}"
            )

        self.current_label_index += 1

    def _wrap_text(self, text, font_name, font_size, max_width):
        """Helper to wrap text to fit within a given width."""
        self.c.setFont(font_name, font_size)
        lines = []
        words = text.split(" ")
        current_line = []
        for word in words:
            # Check if adding the next word exceeds max_width
            test_line = " ".join(current_line + [word])
            if self.c.stringWidth(test_line) <= max_width:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))  # Add the last line
        return lines

    def _fit_text(self, text, font_name, font_size, max_width):
        """Helper to shrink text to fit within a given width."""
        size = font_size
        while size > 6:
            self.c.setFont(font_name, size)
            if self.c.stringWidth(text) <= max_width:
                return size
            else:
                size -= 2
        return size

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
        return None

    try:
        with open(config_file_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"ERROR: Could not parse YAML file '{config_file_path}': {e}")
        return None


# --- Main Script Execution ---


def main():
    global DISCOGS_USER_TOKEN, DISCOGS_COLLECTION_FOLDER  # Declare global to modify them

    # Load configuration
    config = load_config(CONFIG_FILE)
    if not config:
        return

    DISCOGS_USER_TOKEN = config.get("discogs_user_token")
    DISCOGS_COLLECTION_FOLDER = config.get("discogs_collection_folder")
    test_count = config.get("test_count", 9999)  # limit query number

    if not DISCOGS_USER_TOKEN:
        print(
            "ERROR: 'discogs_user_token' missing in the configuration file."
        )
        print(
            "Please ensure your 'discogs_labels_config.yaml' file contains the token."
        )
        return

    print("--- Starting Discogs Jukebox Label Generator ---")
    print(f"Fetching from folder: {DISCOGS_COLLECTION_FOLDER}")

    # Initialize the Discogs client using the discogs-client library
    # 'User-Agent' is automatically handled by discogs-client
    # 'request_limit_interval' and 'request_limit' can be adjusted if needed for rate limiting
    d = discogs_client.Client(
        "DiscogsJukeboxLabelGenerator/1.0", user_token=DISCOGS_USER_TOKEN
    )
    pdf_generator = JukeboxLabelPDFGenerator(OUTPUT_PDF_FILENAME, config)

    try:
        # Get the user object
        user = d.identity()
        print(f"Authenticated as Discogs user: {user.username}")

        # Find the target folder by name
        target_folder = None
        if DISCOGS_COLLECTION_FOLDER:
            for folder in user.collection_folders:
                if folder.name == DISCOGS_COLLECTION_FOLDER:
                    target_folder = folder
                    break
        
        if not target_folder:
            print(f"ERROR: Could not find a Discogs collection folder named '{DISCOGS_COLLECTION_FOLDER}'.")
            folder_names = [f.name for f in user.collection_folders]
            if folder_names:
                print(f"Available folders are: {', '.join(folder_names)}")
            else:
                print("You have no collection folders.")
            return

        # Fetch collection releases from the found folder
        collection_releases = []
        print(f"Fetching collection for user: {user.username} from folder '{target_folder.name}'...")
        for release_item in target_folder.releases:
            if len(release_item.release.tracklist) > 2:
                print(
                    f"Examine: {release_item.release.title} by {', '.join([a.name for a in release_item.release.artists])}"
                )
                for track in release_item.release.tracklist:
                    print(f"  Track {track.position} : {track.title}")
            collection_releases.append(
                release_item.release
            )  # Get the actual Release object from the CollectionRelease object
            print(
                f"Adding: {release_item.release.title} by {', '.join([a.name for a in release_item.release.artists])}"
            )
            if len(collection_releases) == test_count:
                break
            time.sleep(1.0)  # throttle our calls

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
        print(
            "Please check your Discogs User Token and Username in the configuration file."
        )
    except requests.exceptions.RequestException as e:
        print(f"Network or request error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during execution: {e}")


if __name__ == "__main__":
    main()
