import pytest
import psycopg2
from psycopg2 import Error

# Test database configuration
TEST_DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "database": "test_dry_bridge_db",
    "user": "dev_user",
    "password": "Password123!@#",
}


def pytest_configure(config):
    """Set up test database before running tests"""
    try:
        # Connect to default postgres database to create test database
        conn = psycopg2.connect(
            host=TEST_DB_CONFIG["host"],
            port=TEST_DB_CONFIG["port"],
            database="postgres",
            user=TEST_DB_CONFIG["user"],
            password=TEST_DB_CONFIG["password"],
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Drop test database if it exists
        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}")

        # Create test database
        cursor.execute(f"CREATE DATABASE {TEST_DB_CONFIG['database']}")

        cursor.close()
        conn.close()

    except Error as e:
        pytest.fail(f"Failed to set up test database: {e}")


def pytest_unconfigure(config):
    """Clean up test database after tests"""
    try:
        # Connect to default postgres database to drop test database
        conn = psycopg2.connect(
            host=TEST_DB_CONFIG["host"],
            port=TEST_DB_CONFIG["port"],
            database="postgres",
            user=TEST_DB_CONFIG["user"],
            password=TEST_DB_CONFIG["password"],
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Drop test database
        cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}")

        cursor.close()
        conn.close()

    except Error as e:
        print(f"Warning: Failed to clean up test database: {e}")
