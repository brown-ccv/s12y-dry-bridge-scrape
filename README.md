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

## PostgreSQL Integration

The `postgres_scrape.py` script extends the basic scraping functionality by storing the data in a PostgreSQL database. This allows for persistent storage and easier data analysis.

### Database Setup

1. Create a PostgreSQL database and user:
```sql
CREATE USER dev_user WITH PASSWORD 'Password123!@#';
CREATE DATABASE dry_bridge_db OWNER dev_user;
GRANT ALL PRIVILEGES ON DATABASE dry_bridge_db TO dev_user;
```

2. Take `example.env` and create a copy called `.env` 
Update the variables with your database credentials.

### Running the PostgreSQL Scraper

The `postgres_scrape.py` script supports the same time range options as `scrape.py`:

```
python postgres_scrape.py -r 3day
```

Or with a specific date range:

```
python postgres_scrape.py -s 2023-08-31 -e 2024-08-01
```

### Database Schema

The script creates a table called `solar_production` with the following structure:
- `timestamp`: TIMESTAMP (Primary Key)
- `kw`: FLOAT (Power in kilowatts)
- `kwh`: FLOAT (Energy in kilowatt-hours)
- `mmbtu`: FLOAT (Energy in million British thermal units)
- `mtco2e`: FLOAT (Carbon dioxide equivalent in metric tons)

### Data Export

To export the data from the database to a CSV file:

```sql
\copy (SELECT * FROM solar_production ORDER BY timestamp) TO 'solar_production_export.csv' WITH CSV HEADER;
```

### Testing

The project includes test cases in the `tests` directory. Run the tests using:

```
pytest tests/
```

Note: Tests require a test database named `test_dry_bridge_db` with the same user credentials as the main database.
