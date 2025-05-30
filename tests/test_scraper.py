import pytest
import pandas as pd
import datetime
import os
import psycopg2
from psycopg2 import Error
from io import StringIO
from postgres_scrape import process_inverter_data, create_tables, insert_solar_data

# Local postgres test database needed for testing
# Below are the configuration details for the test database
TEST_DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'test_dry_bridge_db',
    'user': 'dev_user',
    'password': 'Password123!@#'
}

def get_test_db_connection():
    try:
        connection = psycopg2.connect(**TEST_DB_CONFIG)
        return connection
    except Error as e:
        pytest.fail(f"Failed to connect to test database: {e}")

@pytest.fixture
def test_db():
    """Fixture to set up and tear down test database"""
    connection = get_test_db_connection()
    create_tables(connection)
    yield connection
    # Clean up after tests
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS solar_production")
    connection.commit()
    cursor.close()
    connection.close()

def insert_csv_from_string(connection, csv_content):
    """Helper function to insert CSV data from a string in tests"""
    # Create a temporary test data file
    temp_path = './test_data.csv'
    try:
        # Write content to temp file
        with open(temp_path, 'w') as f:
            f.write(csv_content)
        # Use the regular insert_solar_data function
        insert_solar_data(connection, temp_path)
    finally:
        # Remove temp file afterwards
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_process_inverter_data():
    # Test normal case
    timestamp = datetime.datetime(2025, 1, 1, 12, 0)
    result = process_inverter_data(timestamp, 100.0)
    
    assert result['timestamp'] == timestamp
    assert result['kw'] == 100.0
    assert result['kwh'] == 25.0  # 100 * 0.25
    assert abs(result['mmbtu'] - 0.0853) < 0.0001
    assert abs(result['mtco2e'] - 0.00592) < 0.0001

    # Test zero value
    result = process_inverter_data(timestamp, 0.0)
    assert result['kw'] == 0.0
    assert result['kwh'] == 0.0
    assert result['mmbtu'] == 0.0
    assert result['mtco2e'] == 0.0

    # Test negative value
    result = process_inverter_data(timestamp, -10.0)
    assert result['kw'] == -10.0
    assert result['kwh'] == -2.5
    assert abs(result['mmbtu'] - -0.00853) < 0.0001
    assert abs(result['mtco2e'] - -0.000592) < 0.0001


def test_database_operations(test_db):
    # Test table creation
    cursor = test_db.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'solar_production'
        );
    """)
    assert cursor.fetchone()[0] is True

    # Test data insertion
    test_data = [
        (datetime.datetime(2025, 1, 1, 12, 0), 100.0, 25.0, 0.0853, 0.00592),
        (datetime.datetime(2025, 1, 1, 12, 15), 150.0, 37.5, 0.12795, 0.00888)
    ]
    
    cursor.executemany('''
        INSERT INTO solar_production 
        (timestamp, kw, kwh, mmbtu, mtco2e)
        VALUES (%s, %s, %s, %s, %s)
    ''', test_data)
    test_db.commit()

    # Check data
    cursor.execute('SELECT * FROM solar_production ORDER BY timestamp')
    results = cursor.fetchall()
    assert len(results) == 2
    assert results[0][0] == datetime.datetime(2025, 1, 1, 12, 0)
    assert results[0][1] == 100.0
    assert results[1][0] == datetime.datetime(2025, 1, 1, 12, 15)
    assert results[1][1] == 150.0

# CSV Processing Tests
def test_csv_processing(test_db):
    # Use the existing mock_data.csv file
    csv_path = os.path.join(os.path.dirname(__file__), 'mock_data.csv')
    
    # Test valid CSV processing
    insert_solar_data(test_db, csv_path)
    
    # Verify data was inserted
    cursor = test_db.cursor()
    cursor.execute('SELECT COUNT(*) FROM solar_production')
    count = cursor.fetchone()[0]
    assert count > 0, f"Expected data to be inserted, but got {count} rows"
    
    # Verify specific data points
    cursor.execute('SELECT timestamp, kw FROM solar_production ORDER BY timestamp')
    rows = cursor.fetchall()
    
    # Check that we have valid data
    for row in rows:
        assert isinstance(row[0], datetime.datetime), f"Expected timestamp, got {type(row[0])}"
        assert isinstance(row[1], (int, float)), f"Expected numeric kw value, got {type(row[1])}" 