# Dry Bridge Scrape

Quick script to pull the CSV data from [Brown's new solar investment](https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US). This script uses `playwright` to handle the scraping part. There was some tricky auth stuff I didn't want to deal with

## Getting Started


(Optional) Create a virtual environment

```
python3 -m venv .venv
source ./.venv/bin/activate
```

First install the requirements

```
pip install -r requirements.txt
```

Then install the `playwright` utilities

```
playwright install
```

And finally run the script

```
python scrape.py
```

The results will be saved in `chart.csv`
