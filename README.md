# Quick Explainer #

I want to use Discogs to catalog all my jukebox singles.

I want to be able to print jukebox title strips from those collections.

## Example Output

[Default Color](examples/example_output_default.pdf)


[Green Color](examples/example_output_green.pdf)

## Install dependencies

Clone the repository or download the project as a zip and extract it.
Make sure you have python3.10 or newer installed.

On Linux in the project directory.
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Windows open a CMD window.
Get into the project directory in the CMD window, run the following commands.
```
python3.exe -m venv venv
source venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy **discogs_labels_config_example.yaml** to **discogs_labels_config.yaml** and edit.
```
cp discogs_labels_config_example.yaml discogs_labels_config.yaml
nano discogs_labels_config.yaml
```
Set **discogs_username** and **discogs_user_token**

## How to use this

1. In Discogs create a custom folder for each jukebox or label style/color.
2. Move your collection items to the appropriate folder.
3. Change the **discogs_collection_folder** in the yaml file, it takes trial and error here.
4. Run the script `discogs_labels.py`
5. View the generated PDF file **Discogs_Jukebox_Labels.pdf**

You can change the output color in the config file using:
```
label_color: "#FF0000"  # RGB color, this would be Red
```

Select one of the other styles using **label_template**

There are other configurations you can play with, see them in the script.

## Automatic Identification of Singles

The `auto_id.py` script can identify a vinyl single by listening to it through your microphone. It uses the ACRCloud service to identify the song and then searches for it on Discogs.

### Configuration for Automatic Identification

1.  Copy `id_config_example.yaml` to `id_config.yaml`.
    ```
    cp id_config_example.yaml id_config.yaml
    nano id_config.yaml
    ```
2.  Edit `id_config.yaml` and fill in your ACRCloud and Discogs API credentials. You will need to create accounts on both services to get these credentials.

### How to use the Automatic Identification

1.  Run the script:
    ```
    python3 auto_id.py
    ```
2.  The script will record 10 seconds of audio from your microphone.
3.  If the song is identified, it will print the song's information and a list of matching vinyl singles from Discogs.

