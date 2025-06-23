# Quick Explainer #

I want to use Discogs to catalog all my jukebox singles.

I want to be able to print jukebox title strips from those collections.

## Example Output
[Default Color](examples/example_output_default.pdf)
[Green Color](examples/example_output_green.pdf)

## Install dependencies
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## How to use this

1. In Discogs create a custom folder for each jukebox or label style/color.
2. Move your collection items to the appropriate folder.
3. Change the **discogs_collection_folder** in the yaml file.
4. Run the script `discogs_labels.py`
5. View the generated PDF file **Discogs_Jukebox_Labels.pdf**

You can change the output color in the config file using:
```
label_color: "#FF0000"  # RGB color, this would be Red
```
