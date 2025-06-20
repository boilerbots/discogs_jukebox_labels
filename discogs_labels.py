import requests
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black
import time # For rate limiting

# --- Configuration ---
DISCOGS_USER_TOKEN = ""
DISCOGS_USERNAME = ""

OUTPUT_PDF_FILENAME = "Discogs_Jukebox_Labels.pdf"

# Jukebox Label Dimensions (adjust as needed)
# Typical jukebox labels are around 3-4 inches tall and 1-1.5 inches wide,
# often fitting 2-3 per row on an 8.5x11 sheet.
LABEL_WIDTH = 3.0 * inch
LABEL_HEIGHT = 1.0 * inch

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

# --- Discogs API Client ---

class DiscogsClient:
    """
    A client to interact with the Discogs API.
    Handles authentication and fetching user collection data.
    """
    def __init__(self, user_token, username):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "DiscogsJukeboxLabelGenerator/1.0", # Required by Discogs API
            "Authorization": f"Discogs token={user_token}"
        }
        self.username = username

    def _make_request(self, endpoint, params=None, max_retries=3, delay_seconds=1):
        """
        Makes a GET request to the Discogs API with error handling and rate limiting.
        """
        url = f"{self.base_url}{endpoint}"
        print(f"Requesting: {url} with params: {params}")
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                # Check for Discogs rate limit headers if available
                # current_requests = response.headers.get('X-Discogs-Ratelimit-Current')
                # limit_requests = response.headers.get('X-Discogs-Ratelimit-Limit')
                # remaining_requests = response.headers.get('X-Discogs-Ratelimit-Remaining')
                # print(f"Rate Limit: {remaining_requests}/{limit_requests} requests remaining.")

                time.sleep(delay_seconds) # Respect rate limits, default 1 second delay
                return response.json()
            except requests.exceptions.HTTPError as e:
                print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
                if e.response.status_code == 429: # Too Many Requests
                    print(f"Rate limit hit. Retrying in {delay_seconds * (attempt + 1)} seconds...")
                    time.sleep(delay_seconds * (attempt + 1)) # Exponential backoff
                else:
                    print(f"Request failed: {e}. Attempt {attempt + 1} of {max_retries}")
                    if attempt == max_retries - 1:
                        raise
            except requests.exceptions.ConnectionError as e:
                print(f"Connection Error: {e}. Attempt {attempt + 1} of {max_retries}")
                time.sleep(delay_seconds * (attempt + 1))
                if attempt == max_retries - 1:
                    raise
            except requests.exceptions.Timeout as e:
                print(f"Timeout Error: {e}. Attempt {attempt + 1} of {max_retries}")
                time.sleep(delay_seconds * (attempt + 1))
                if attempt == max_retries - 1:
                    raise
            except Exception as e:
                print(f"An unexpected error occurred: {e}. Attempt {attempt + 1} of {max_retries}")
                time.sleep(delay_seconds * (attempt + 1))
                if attempt == max_retries - 1:
                    raise
        return None

    def get_collection(self):
        """
        Fetches all releases from the user's Discogs collection.
        Handles pagination automatically.
        """
        collection_releases = []
        page = 1
        total_pages = 1

        print(f"Fetching collection for user: {self.username}...")

        while page <= total_pages:
            endpoint = f"/users/{self.username}/collection/folders/0/releases" # Folder 0 is "All"
            params = {"page": page, "per_page": 50} # Fetch 50 releases per page
            data = self._make_request(endpoint, params=params)

            if data and "releases" in data:
                collection_releases.extend(data["releases"])
                pagination = data.get("pagination", {})
                total_pages = pagination.get("pages", 1)
                print(f"Fetched page {page}/{total_pages}. Total releases fetched: {len(collection_releases)}")
                page += 1
            else:
                print("No releases found or unexpected data structure.")
                break
        print(f"Finished fetching collection. Total releases: {len(collection_releases)}")
        return collection_releases

    def get_release_details(self, release_id):
        """
        Fetches detailed information for a specific Discogs release.
        This is useful to get label and catalog number from the main release,
        as collection entries might sometimes reference master releases.
        """
        endpoint = f"/releases/{release_id}"
        return self._make_request(endpoint)

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

    def add_label(self, release_data):
        """
        Adds a single jukebox label to the PDF. Manages page breaks.
        """
        if self.current_label_index >= LABELS_PER_PAGE:
            self.c.showPage()
            self.current_label_index = 0
            self.current_page_number += 1
            print(f"Starting new page: {self.current_page_number}")

        x, y = self._calculate_position(self.current_label_index)

        # Draw the label border (optional, but good for visual debugging)
        self.c.rect(x, y, LABEL_WIDTH, LABEL_HEIGHT)

        # Extract information
        artist = release_data.get("artist_name", "Unknown Artist")
        title = release_data.get("title", "Unknown Title")
        label_name = "Unknown Label"
        catalog_number = "N/A"

        # Try to get label and catalog from release details if available and collection item is a master
        # Collection items directly link to releases, not masters for label info
        # The 'basic_information' usually has the label and catno.
        if "labels" in release_data.get("basic_information", {}) and release_data["basic_information"]["labels"]:
            # Often there can be multiple labels, take the first one or primary
            primary_label = release_data["basic_information"]["labels"][0]
            label_name = primary_label.get("name", label_name)
            catalog_number = primary_label.get("catno", catalog_number)
        elif "labels" in release_data and release_data["labels"]: # Sometimes directly in release_data from details
            primary_label = release_data["labels"][0]
            label_name = primary_label.get("name", label_name)
            catalog_number = primary_label.get("catno", catalog_number)

        # Content positioning within the label
        text_x = x + 0.05 * inch # Small padding from left edge
        text_width = LABEL_WIDTH - 0.1 * inch

        # Title (usually prominent)
        self.c.setFont("Helvetica-Bold", 10)
        # Wrap title if it's too long
        title_lines = self._wrap_text(title, "Helvetica-Bold", 10, text_width)
        # Position title near the top of the label
        title_y_start = y + LABEL_HEIGHT - 0.15 * inch
        for line in title_lines:
            self.c.drawString(text_x, title_y_start, line)
            title_y_start -= 0.15 * inch # Move down for next line

        # Artist (below title)
        self.c.setFont("Helvetica", 8)
        artist_lines = self._wrap_text(artist, "Helvetica", 8, text_width)
        artist_y_start = title_y_start - 0.1 * inch # Space below title
        for line in artist_lines:
            self.c.drawString(text_x, artist_y_start, line)
            artist_y_start -= 0.12 * inch # Move down for next line

        # Label and Catalog Number (at the bottom)
        self.c.setFont("Helvetica", 7)
        self.c.drawString(text_x, y + 0.15 * inch, f"Label: {label_name}")
        self.c.drawString(text_x, y + 0.05 * inch, f"Cat#: {catalog_number}")

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

# --- Main Script Execution ---

def main():
    if DISCOGS_USER_TOKEN == "YOUR_DISCOGS_USER_TOKEN" or DISCOGS_USERNAME == "YOUR_DISCOGS_USERNAME":
        print("ERROR: Please update DISCOGS_USER_TOKEN and DISCOGS_USERNAME in the script.")
        print("You can get your Discogs user token from: https://www.discogs.com/settings/developers")
        return

    print("--- Starting Discogs Jukebox Label Generator ---")

    discogs = DiscogsClient(DISCOGS_USER_TOKEN, DISCOGS_USERNAME)
    pdf_generator = JukeboxLabelPDFGenerator(OUTPUT_PDF_FILENAME)

    try:
        collection_releases = discogs.get_collection()

        if not collection_releases:
            print("No releases found in your collection. Exiting.")
            return

        print(f"\nGenerating labels for {len(collection_releases)} releases...")
        for i, release_item in enumerate(collection_releases):
            # Collection items have 'basic_information' which often contains what we need.
            # If not, we might need to fetch full release details.
            # For simplicity, we'll use basic_information first.
            artist_name = ", ".join([a['name'] for a in release_item['basic_information'].get('artists', [])])
            title = release_item['basic_information'].get('title')
            # Extract label and catno from basic_information.labels
            labels_info = release_item['basic_information'].get('labels', [])
            release_data_for_label = {
                "artist_name": artist_name,
                "title": title,
                "labels": labels_info, # Pass the full labels list
                "basic_information": release_item['basic_information'] # For robustness
            }
            pdf_generator.add_label(release_data_for_label)
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1} labels...")

        pdf_generator.save_pdf()
        print("--- Discogs Jukebox Label Generator Finished ---")

    except Exception as e:
        print(f"An error occurred during execution: {e}")

if __name__ == "__main__":
    main()

