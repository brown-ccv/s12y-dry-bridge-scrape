# Dry Bridge Solar Data ETL

An ETL (Extract, Transform, Load) pipeline for collecting and processing solar production data from [Dry Bridge Solar Farm](https://hmi.alsoenergy.com/powerhmi/publicdisplay/be7a7484-25f9-4b3e-a3ac-637ca6111cf3/main?arg=NTk0NDk%3d&lang=en-US). This pipeline extracts data via web scraping, transforms it into standardized energy metrics, and loads it into a PostgreSQL database for analysis

## Installation

This project uses modern Python tooling for dependency management and development. Choose one of the installation methods below:

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the project and its dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate
```

## Configuration

### Environment Setup

Copy the example environment file:
```bash
cp env.example .env
```

The `env.example` file contains credentials to connect to the docker development database. When you're ready to upload data to production, edit `.env` with the production database credentials

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dry_bridge_db
DB_USER=your_username
DB_PASSWORD=your_password
```

### Database Setup

The database is setup and managed by the DBA team. The Office of Sustainability and Resiliency is the data owner

## Usage

The application provides a CLI interface with two main commands: `extract` and `load`.

### Extracting Data

Extract solar data from the web dashboard:

```bash
# Extract all available data (from July 1, 2023 to now) into ./output
dry-bridge extract

# Extract data for a specific date range
dry-bridge extract -s 2023-08-01 -e 2024-08-01

# Resume a previous extraction
dry-bridge extract --resume

# Extract to a custom output directory
dry-bridge extract --output ./custom_output
```

### Loading Data

Load extracted data into the database:

```bash
# Load both raw and processed data
dry-bridge load

# Load only raw data
dry-bridge load --no-transform

# Load only processed data  
dry-bridge load --no-raw

# Load from custom output directory
dry-bridge load ./custom_output
```

### Complete ETL Pipeline

For a complete ETL run:

```bash
# Extract all data and load into database
dry-bridge extract && dry-bridge load
```

## Database Schema

The application creates two tables:

### `dry_bridge_solar_processed`
- `timestamp` (TIMESTAMP, PRIMARY KEY): UTC timestamp
- `kw` (FLOAT): Power in kilowatts
- `kwh` (FLOAT): Energy in kilowatt-hours
- `mmbtu` (FLOAT): Energy in million British thermal units
- `mtco2e` (FLOAT): Carbon dioxide equivalent in metric tons avoided

### `dry_bridge_solar_raw`
- `timestamp` (TEXT): Original timestamp string
- `name` (TEXT): Measurement source name
- `type` (TEXT): Measurement type
- `units` (TEXT): Units of measurement
- `value` (FLOAT): Raw measurement value

## Data Export

Export processed data to CSV:

```sql
\copy (SELECT * FROM dry_bridge_solar_processed ORDER BY timestamp) TO 'solar_production_export.csv' WITH CSV HEADER;
```

## Development

### Development Setup

```bash
# Install with development dependencies
uv sync
```

### Code Quality

This project uses several tools for code quality:

```bash
# Linting with ruff
uv run ruff check .

# Code formatting with ruff
uv run ruff format .

# Type checking
uv run mypy src/

# Dependency checking
uv run deptry .
```

### Testing

Run the test suite:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=dry_bridge

# Run specific test file
uv run pytest tests/transform_test.py
```

**Note**: Tests require a test database named `test_dry_bridge_db` with the same user credentials.

## Project Structure

```
src/dry_bridge/
├── __init__.py          # Package initialization and documentation
├── __main__.py          # CLI application entry point
├── scrape.py           # Web scraping functionality
├── transform.py        # Data transformation and calculations
└── load.py             # Database operations and loading

tests/
├── data/               # Test data files
└── transform_test.py   # Unit tests

# Configuration files
├── pyproject.toml      # Project metadata and dependencies
├── mise.toml          # Tool version management
├── uv.lock            # Locked dependency versions
└── .env.example       # Environment variable template
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**: The scraper relies on session cookies from the dashboard. If you encounter authentication issues, the dashboard may have changed its authentication mechanism.

2. **Database Connection**: Ensure PostgreSQL is running and your credentials in `.env` are correct.

3. **Missing Data**: Some days may have no data available from the solar farm. This is normal and will be logged as failed downloads.

4. **Timezone Issues**: The application handles Eastern time to UTC conversion automatically, accounting for daylight saving time transitions.

### Logging

The application uses Python's standard logging. To increase verbosity:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## License

This project is for internal use with the Dry Bridge solar farm data monitoring.
