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

Run the script to get CSV with a given time range

```
python scrape.py -r 3day
```

The results will be saved in `chart-3day.csv`

Or run the script with a given date range. The output files will look like
`chart-YYYY-MM-DD.csv`. If an end date is not provided, the script assumes today

```
python scrape.py -s 2023-08-31 -e 2024-08-01
```
