import csv
import time
import os
import board
import sys
import adafruit_dht
from datetime import datetime
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
from loguru import logger

logger.remove() # Remove default Loguru Handler
logger.add(
    sys.stdout, 
    format="[{time:HH:mm:ss}] {level}: {message}", 
    level="INFO"
    )

logger.add(
    "/app/logs/logger.log", 
    format="[{time:YYYY-MM-DD HH:mm:ss}] {level}: {message}",
    level="INFO", 
    rotation="10MB"
    )

logger.info("Starting DHT logger...")  # Debugging message

# ENVS
LOG_INTERVAL = int(os.getenv("LOG_INTERVAL", 60)) # Default 60 seconds if not set
DHT_PIN = os.getenv("DHT_PIN", "D4")  # Default to D4 if not set
DHT_RETRIES = int(os.getenv("DHT_RETRIES", 3)) # Default 3 retries if not set

DHT_SENSOR_NAME = os.getenv("DHT_SENSOR_NAME", f"sensor_{DHT_PIN}")

logger.info(f"Using DHT_PIN: {DHT_PIN}")  # Debugging message
logger.info(f"Logging interval: {LOG_INTERVAL} seconds")  # Debugging message
logger.info(f"Number of retries for sensor read: {DHT_RETRIES}")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086") 
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my_secret_token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "my_org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")

logger.info(f"InfluxDB url: {INFLUXDB_URL}")  # Debugging message
logger.info(f"InfluxDB organization: {INFLUXDB_ORG}")  # Debugging message
logger.info(f"InfluxDB bucket: {INFLUXDB_BUCKET}")  # Debugging message

# Ensure CSV directory exists
data_folder = os.path.join('/app/data/', DHT_SENSOR_NAME)
os.makedirs(data_folder, exist_ok=True)
logger.info(f"Directory created or already exists: {data_folder}")

logger.info("Initializing DHT sensor...")  # Debugging message
# Convert pin string to board attribute dynamically
try:
    DHT_PIN = getattr(board, DHT_PIN)
    logger.success(f"GPIO Pin initialized successfully (DHT pin: {DHT_PIN}).")
except AttributeError:
    logger.error(f"Invalid GPIO pin specified: {DHT_PIN}")
    exit(1)

# Initialize DHT sensor
dht_sensor = adafruit_dht.DHT22(DHT_PIN, use_pulseio=False)
logger.info("DHT sensor initialiazed.")  # Debugging message

logger.info(f"Initializing InfluxDB connection: URL: {INFLUXDB_URL} ORG: {INFLUXDB_ORG}")  # Debugging message

# Initialize InfluxDB client
try:
    client = influxdb_client.InfluxDBClient(
        url=INFLUXDB_URL, 
        token=INFLUXDB_TOKEN, 
        org=INFLUXDB_ORG
        )
    write_api = client.write_api(write_options=SYNCHRONOUS)
    logger.success("Connected to InfluxDB successfully.")  # Debugging message
except Exception as e:
    logger.error(f"Failed to connect to InfluxDB: {e}")
    influx_client = None # Prevent further failures

logger.info("Ensuring CSV file exists...")
# Function to get today's CSV filename
def get_csv_filename():
    return os.path.join('/app/data', DHT_SENSOR_NAME, datetime.now().strftime("%Y-%m-%d") + ".csv")

# Ensure CSV file has a header if it's newly created
def initialize_csv():
    filename = get_csv_filename()
    if not os.path.exists(filename):
        logger.info(f"Creating new CSV file: {filename}")
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([f"# Sensor Name: {DHT_SENSOR_NAME}, Pin: {DHT_PIN}, InfluxDB Org: {INFLUXDB_ORG}, InfluxDB Bucket: {INFLUXDB_BUCKET}"])
            writer.writerow(["date", "time", "temperature", "humidity"])
    return filename

def log_temperature():
    logger.info("Attempting to read sensor data...")
    
    sensor_id = DHT_SENSOR_NAME
    
    filename = initialize_csv()

    temperature = None
    humidity = None

    for attempt in range(1, DHT_RETRIES + 1):
        try:
            temperature = dht_sensor.temperature
            humidity = dht_sensor.humidity

            if humidity is not None and temperature is not None:
                break  # Valid reading, exit loop

            logger.warning(f"Attempt {attempt}/{DHT_RETRIES}: Invalid sensor reading, retrying...")
            time.sleep(2)  # Wait before retrying
        except RuntimeError as error:
            logger.warning(f"Attempt {attempt}/{DHT_RETRIES}: Sensor error: {error}, retrying...")
            time.sleep(2)  # Wait before retrying

    if temperature is None or humidity is None:
        logger.error("Failed to get valid temperature or humidity data.")
        return
    
    # Read time
    now = datetime.now()
    now_db = now.isoformat() + "Z" # convert date to ISO format for InfluxDB

    logger.info(f"Writing to CSV: Temp={temperature}°C, Humidity={humidity}%, Timestamp={now}")

    try:
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with open(filename, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date_str, time_str, temperature, humidity])
        logger.success(f"Successfully written to CSV: {date_str} {time_str} - Temp={temperature:.1f}°C, Humidity={humidity:.1f}% (CSV filename: {filename})")
    
    except Exception as e:
        logger.error(f"Error writing to CSV file: {e}")

    # Debugging print before writing
    logger.info(f"Writing to DB: Temp={temperature}°C, Humidity={humidity}%, Timestamp={now_db}")

    try:
        p = (
            influxdb_client.Point("temperature_humidity")
            .tag("sensor_id", sensor_id)
            .field("temperature", temperature)
            .field("humidity", humidity)
            .time(now_db)
        )

        write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=p)
        logger.success(f"Successfully written to DB: Temp={temperature}°C, Humidity={humidity}% with tag={sensor_id} at {now_db}")

    except Exception as e:
        logger.error(f"Error writing to DB: {e}")
   

if __name__ == "__main__":
    logger.info("Ensuring CSV file exists...")
    initialize_csv()  # Ensure CSV file exists at startup

    next_run_time = time.monotonic()  # Get precise start time
    logger.info("Starting measurement loop...")

    try:
        while True:
            log_temperature()
            next_run_time += LOG_INTERVAL  # Schedule the next exact run time
            sleep_time = max(0, next_run_time - time.monotonic())  # Ensure we never sleep negative
            logger.info(f"Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("\n Stopping logger...")
    # Ensure propper cleanup when exiting
    if influx_client:
        write_api.close()
        client.close()
        logger.info("InfluxDB connection closed.")
    logger.info("Logger stopped")

