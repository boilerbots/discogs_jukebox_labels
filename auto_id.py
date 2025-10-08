import sounddevice as sd
import wave
import os
import json
import base64
import hashlib
import hmac
import time
import requests
import yaml
import numpy as np
from datetime import datetime

class ACRCloudRecognizer:
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
        string_to_sign = http_method + "\n" + http_uri + "\n" + self.access_key + "\n" + data_type + "\n" + signature_version + "\n" + timestamp
        sign = base64.b64encode(
            hmac.new(self.access_secret.encode('utf-8'), 
                    string_to_sign.encode('utf-8'), 
                    digestmod=hashlib.sha1).digest()
        ).decode('utf-8')
        
        # Prepare the request
        with open(audio_file, 'rb') as f:
            sample_bytes = f.read()
        
        files = {'sample': (audio_file, sample_bytes)}
        data = {
            'access_key': self.access_key,
            'sample_bytes': len(sample_bytes),
            'timestamp': timestamp,
            'signature': sign,
            'data_type': data_type,
            'signature_version': signature_version
        }
        
        url = f"https://{self.host}{http_uri}"
        response = requests.post(url, files=files, data=data)
        return response.json()


class DiscogsClient:
    def __init__(self, user_agent, token=None, country="US"):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            'User-Agent': user_agent
        }
        if token:
            self.headers['Authorization'] = f'Discogs token={token}'
        
        self.username = None
        self.slot_field_id = None
        self.country = country
        
        # Fetch username and custom field ID on initialization
        if token:
            self.username = self._fetch_username()
            if self.username:
                self.slot_field_id = self._fetch_slot_field_id()
    
    def _fetch_username(self):
        """Fetch the authenticated username"""
        url = f"{self.base_url}/oauth/identity"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get('username')
        return None
    
    def _fetch_slot_field_id(self):
        """Fetch the custom field ID for 'Slot' field"""
        if not self.username:
            return None
        
        url = f"{self.base_url}/users/{self.username}/collection/fields"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            fields = response.json().get('fields', [])
            for field in fields:
                if field.get('name', '').lower() == 'slot':
                    field_id = field.get('id')
                    print(f"✓ Found 'Slot' custom field (ID: {field_id})")
                    return field_id
            
            print("Warning: 'Slot' custom field not found in your Discogs collection.")
            print("Please create a custom field named 'Slot' in your Discogs collection settings.")
            return None
        else:
            print(f"Error fetching custom fields: {response.status_code}")
            return None
    
    def search_vinyl_single(self, artist, title):
        """Search for vinyl singles on Discogs"""
        params = {
            'artist': artist,
            'release_title': title,
            'format': 'Vinyl',
            'type': 'release'
        }
        
        url = f"{self.base_url}/database/search"
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            all_results = data.get('results', [])
            
            # First pass: Filter for singles/7" records from specified country
            singles = []
            for result in all_results:
                formats = result.get('format', [])
                country = result.get('country', '')
                
                # Check if it's a single/7"/45 RPM
                is_single = all(fmt in str(formats).lower() for fmt in ['single', '7"', '45'])
                
                if is_single and country == self.country:
                    singles.append(result)
            
            # If no results with country filter, try without country filter
            if len(singles) == 0:
                print(f"  No results found for country '{self.country}', searching all countries...")
                for result in all_results:
                    formats = result.get('format', [])
                    is_single = any(fmt in str(formats).lower() for fmt in ['single', '7"', '45'])
                    
                    if is_single:
                        singles.append(result)
            
            # If still no results, return all results without any filtering
            if len(singles) == 0:
                print(f"  No singles found, returning all vinyl results...")
                singles = all_results
            
            return singles
        else:
            return []
    
    def get_username(self):
        """Get the authenticated username"""
        return self.username
    
    def create_folder(self, folder_name):
        """Create a new collection folder"""
        username = self.get_username()
        if not username:
            print("Error: Could not authenticate with Discogs")
            return None
        
        url = f"{self.base_url}/users/{username}/collection/folders"
        data = {'name': folder_name}
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code == 201:
            folder_id = response.json().get('id')
            print(f"✓ Created new collection folder: {folder_name} (ID: {folder_id})")
            return folder_id
        else:
            print(f"Error creating folder: {response.status_code} - {response.text}")
            return None
    
    def add_to_collection(self, folder_id, release_id, slot_number):
        """Add a release to collection folder with custom slot field"""
        if not self.username:
            print("Error: Not authenticated with Discogs")
            return False
        
        url = f"{self.base_url}/users/{self.username}/collection/folders/{folder_id}/releases/{release_id}"
        
        # Add the release first
        response = requests.post(url, headers=self.headers)
        
        if response.status_code == 201:
            instance_id = response.json().get('instance_id')
            
            # Update custom field for slot number if we have the field ID
            if self.slot_field_id:
                edit_url = f"{self.base_url}/users/{self.username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}"
                field_url = f"{edit_url}/fields/{self.slot_field_id}"
                
                custom_data = {
                    'value': str(slot_number)
                }
                
                field_response = requests.post(field_url, headers=self.headers, json=custom_data)
                
                if field_response.status_code in [200, 201, 204]:
                    print(f"✓ Added to collection (Slot #{slot_number})")
                else:
                    print(f"✓ Added to collection, but failed to set Slot field: {field_response.status_code}")
            else:
                print(f"✓ Added to collection (Slot field not available)")
            
            return True
        elif response.status_code == 200:
            print("✓ Release already in collection")
            return True
        else:
            print(f"Error adding to collection: {response.status_code} - {response.text}")
            return False


class AudioRecorder:
    def __init__(self, duration=10, sample_rate=44100, channels=1):
        self.duration = duration
        self.sample_rate = sample_rate
        self.channels = channels
        
    def record(self, output_file="temp_recording.wav"):
        """Record audio from microphone"""
        print(f"Recording for {self.duration} seconds...")
        
        # Record audio
        recording = sd.rec(
            int(self.duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16'
        )
        sd.wait()  # Wait until recording is finished
        
        print("Recording complete!")
        
        # Save to WAV file
        with wave.open(output_file, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 2 bytes for int16
            wf.setframerate(self.sample_rate)
            wf.writeframes(recording.tobytes())
        
        return output_file


def get_user_selection(options, max_options):
    """Get user's selection from a list of options"""
    while True:
        try:
            choice = input(f"\nSelect an option (1-{max_options}) or 's' to skip: ").strip().lower()
            if choice == 's':
                return None
            choice_num = int(choice)
            if 1 <= choice_num <= max_options:
                return choice_num - 1
            else:
                print(f"Please enter a number between 1 and {max_options}")
        except ValueError:
            print("Invalid input. Please enter a number or 's' to skip.")


def load_config(config_file='id_config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_file}' not found.")
        print("\nPlease create id_config.yaml with the following format:")
        print("""
acrcloud_access_key: your_access_key_here
acrcloud_access_secret: your_access_secret_here
acrcloud_host: identify-us-west-2.acrcloud.com
discogs_token: your_discogs_token_here
discogs_user_agent: VinylSingleFinder/1.0
discogs_country: US
""")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None


def main():
    # Load configuration from YAML file
    config = load_config()
    if not config:
        return
    
    ACRCLOUD_ACCESS_KEY = config.get('acrcloud_access_key')
    ACRCLOUD_ACCESS_SECRET = config.get('acrcloud_access_secret')
    ACRCLOUD_HOST = config.get('acrcloud_host', 'identify-us-west-2.acrcloud.com')
    DISCOGS_TOKEN = config.get('discogs_token')
    DISCOGS_USER_AGENT = config.get('discogs_user_agent', 'VinylSingleFinder/1.0')
    DISCOGS_COUNTRY = config.get('discogs_country', 'US')
    
    # Validate required fields
    if not all([ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET, DISCOGS_TOKEN]):
        print("Error: Missing required configuration fields.")
        print("Please ensure id_config.yaml contains:")
        print("  - acrcloud_access_key")
        print("  - acrcloud_access_secret")
        print("  - discogs_token")
        return
    
    # Initialize components
    recorder = AudioRecorder(duration=10)
    recognizer = ACRCloudRecognizer(ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET, ACRCLOUD_HOST)
    discogs = DiscogsClient(DISCOGS_USER_AGENT, DISCOGS_TOKEN, DISCOGS_COUNTRY)
    
    print("=== Vinyl Single Collection Manager ===\n")
    
    # Ask user for collection folder name
    folder_name = input("Enter a name for your new collection folder: ").strip()
    if not folder_name:
        print("Error: Folder name cannot be empty")
        return
    
    # Create the collection folder
    folder_id = discogs.create_folder(folder_name)
    if not folder_id:
        print("Failed to create collection folder. Exiting.")
        return
    
    slot_counter = 1
    
    print("\n" + "="*50)
    print("Starting collection process...")
    print("Press Ctrl+C at any time to exit")
    print("="*50 + "\n")
    
    try:
        while True:
            print(f"\n--- Record #{slot_counter} ---")
            input("Press Enter to start recording (or Ctrl+C to exit)...")
            
            # Record audio
            audio_file = recorder.record()
            
            try:
                # Recognize song
                print("\nIdentifying song...")
                result = recognizer.recognize(audio_file)
                
                if result.get('status', {}).get('msg') == 'Success':
                    metadata = result['metadata']['music'][0]
                    title = metadata['title']
                    artists = ', '.join([artist['name'] for artist in metadata['artists']])
                    album = metadata.get('album', {}).get('name', 'Unknown')
                    
                    print(f"\n✓ Song Identified:")
                    print(f"  Title: {title}")
                    print(f"  Artist(s): {artists}")
                    print(f"  Album: {album}")
                    
                    # Search Discogs for vinyl singles
                    print(f"\nSearching Discogs for vinyl singles...")
                    singles = discogs.search_vinyl_single(artists, title)
                    
                    if singles:
                        print(f"\nFound {len(singles)} vinyl single(s):\n")
                        
                        # Show options (limit to 15 for readability)
                        display_count = min(len(singles), 15)
                        for i, single in enumerate(singles[:display_count], 1):
                            print(f"{i}. {single.get('title')}")
                            print(f"   Label: {', '.join(single.get('label', ['Unknown']))}")
                            print(f"   Year: {single.get('year', 'Unknown')}")
                            print(f"   Country: {single.get('country', 'Unknown')}")
                            print(f"   Format: {', '.join(single.get('format', ['Unknown']))}")
                            print()
                        
                        # Get user selection
                        selection_idx = get_user_selection(singles, display_count)
                        
                        if selection_idx is not None:
                            selected = singles[selection_idx]
                            release_id = selected.get('id')
                            
                            print(f"\nSelected: {selected.get('title')}")
                            print(f"Release ID: {release_id}")
                            
                            # Add to collection
                            if discogs.add_to_collection(folder_id, release_id, slot_counter):
                                slot_counter += 1
                        else:
                            print("Skipped. Not added to collection.")
                    else:
                        print("No vinyl singles found on Discogs for this song.")
                        print("Skipping to next record...")
                else:
                    print(f"\nCould not identify song: {result.get('status', {}).get('msg')}")
                    print("Skipping to next record...")
            
            finally:
                # Clean up temporary audio file
                if os.path.exists(audio_file):
                    os.remove(audio_file)
    
    except KeyboardInterrupt:
        print("\n\n=== Collection Process Complete ===")
        print(f"Total records added to '{folder_name}': {slot_counter - 1}")
        print("Exiting...")


if __name__ == "__main__":
    main()
