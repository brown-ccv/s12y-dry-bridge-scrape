"""
Dry Bridge Solar Data ETL Pipeline.

This package provides a complete ETL (Extract, Transform, Load) pipeline for
collecting solar production data from the Dry Bridge solar farm dashboard.

The pipeline consists of three main components:
- Extract: Web scraping of solar data from the dashboard API
- Transform: Data processing and calculation of energy metrics
- Load: Storage of data in PostgreSQL database

Main modules:
- scrape: Web scraping functionality with retry logic and metadata tracking
- transform: Data transformation and metric calculations
- load: Database operations and connection management
- __main__: CLI interface for running the ETL pipeline

Usage:
    This package can be used as a command-line tool via the dry-bridge script
    or imported as a Python module for programmatic use.
"""
