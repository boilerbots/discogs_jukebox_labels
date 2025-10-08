#!/usr/bin/env python3

import pyaudio
import wave
import os
import json
import base64
import hashlib
import hmac
import time
import requests
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
    def __init__(self, user_agent, token=None):
        self.base_url = "https://api.discogs.com"
        self.headers = {
            'User-Agent': user_agent
        }
        if token:
            self.headers['Authorization'] = f'Discogs token={token}'
    
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
            # Filter for singles/7" records
            singles = []
            for result in data.get('results', []):
                formats = result.get('format', [])
                # Look for singles, 7", or 45 RPM in the format description
                #if any(fmt in str(formats).lower() for fmt in ['single', '7"', '45']):
                if any(fmt in str(formats).lower() for fmt in ['single', '7"']):
                    singles.append(result)
            return singles
        else:
            return []


class AudioRecorder:
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
            frames_per_buffer=self.chunk
        )
        
        frames = []
        for i in range(0, int(self.sample_rate / self.chunk * self.duration)):
            data = stream.read(self.chunk)
            frames.append(data)
        
        print("Recording complete!")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Save to WAV file
        wf = wave.open(output_file, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        return output_file


def main():
    # Configuration - Replace with your actual credentials
    ACRCLOUD_ACCESS_KEY = "3f01fb95f1ab94d20198f5162bc37d10"
    ACRCLOUD_ACCESS_SECRET = "6FhAxzhDUjEW8vb4m2B1yzXQBklH86a2B7KlmHrd"
    ACRCLOUD_HOST = "identify-us-west-2.acrcloud.com"
    
    DISCOGS_USER_AGENT = "VinylSingleFinder/1.0"
    DISCOGS_TOKEN = "MSpuVwSxEzwLNGxuynVkGjhfvmOaTWOcEtxKhZaq"
    
    # Initialize components
    recorder = AudioRecorder(duration=10)
    recognizer = ACRCloudRecognizer(ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET, ACRCLOUD_HOST)
    discogs = DiscogsClient(DISCOGS_USER_AGENT, DISCOGS_TOKEN)
    
    print("=== Vinyl Single Identifier ===")
    print("Starting audio capture...")
    
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
            #upc = metadata.get('external_ids', {}).get('upc', 'Unknown')
            
            print(f"\n✓ Song Identified:")
            print(f"  Title: {title}")
            print(f"  Artist(s): {artists}")
            print(f"  Album: {album}")
            #print(f"  upc: {upc}")
            
            # Search Discogs for vinyl singles
            print(f"\nSearching Discogs for vinyl singles...")
            singles = discogs.search_vinyl_single(artists, title)
            
            if singles:
                print(f"\nFound {len(singles)} vinyl single(s):\n")
                for i, single in enumerate(singles[:10], 1):  # Show top 10 results
                    print(f"{i}. {single.get('title')}")
                    print(f"   Label: {', '.join(single.get('label', ['Unknown']))}")
                    print(f"   Year: {single.get('year', 'Unknown')}")
                    print(f"   Country: {single.get('country', 'Unknown')}")
                    print(f"   Format: {', '.join(single.get('format', ['Unknown']))}")
                    print(f"   URL: https://www.discogs.com{single.get('uri', '')}")
                    print()
            else:
                print("No vinyl singles found on Discogs for this song.")
        else:
            print(f"\nCould not identify song: {result.get('status', {}).get('msg')}")
    
    finally:
        # Clean up temporary audio file
        if os.path.exists(audio_file):
            os.remove(audio_file)
            print(f"Cleaned up temporary file: {audio_file}")


if __name__ == "__main__":
    main()
