import csv
import time
import os
import board
import adafruit_dht
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WriteOptions, WritePrecision

print("Starting DHT logger...")  # Debugging message

# Read DHT pin from environment variable (default: board.D4)
LOG_INTERVAL = int(os.getenv("LOG_INTERVAL", 60)) # Default 60 seconds if not set
DHT_PIN_NUMBER = os.getenv("DHT_PIN", "D4")  # Default to D4 if not set
DHT_RETRIES = int(os.getenv("DHT_RETRIES", 3))

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my_secret_token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "my_org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")

print(f"Using DHT_PIN: {DHT_PIN_NUMBER}")  # Debugging message
print(f"Logging interval: {LOG_INTERVAL} seconds")  # Debugging message


# Ensure CSV directory exists
os.makedirs('/app/data', exist_ok=True)

# Convert pin string to board attribute dynamically
try:
    DHT_PIN = getattr(board, DHT_PIN_NUMBER)
    print("GPIO Pin initialized successfully.")
except AttributeError:
    raise ValueError(f"Invalid GPIO pin specified: {DHT_PIN_NUMBER}")
    exit(1)

print("Initializing DHT sensor...")  # Debugging message

# Initialize DHT sensor
dht_sensor = adafruit_dht.DHT22(DHT_PIN, use_pulseio=False)

print("Initializing InfluxDB connection...")  # Debugging message

# Initialize InfluxDB client
try:
    influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    write_api = influx_client.write_api(write_options=WriteOptions(batch_size=1))
    print("Connected to InfluxDB successfully.")  # Debugging message
except Exception as e:
    print(f"Failed to connect to InfluxDB: {e}")
    influx_client = None # Prevent further failures

print("Ensuring CSV file exists...")
# Function to get today's CSV filename
def get_csv_filename():
    return os.path.join('/app/data', datetime.now().strftime("%Y-%m-%d") + ".csv")

# Ensure CSV file has a header if it's newly created
def initialize_csv():
    filename = get_csv_filename()
    if not os.path.exists(filename):
        print(f"Creating new CSV file: {filename}")
        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["date", "time", "temperature", "humidity"])
    return filename

# Function to log temperature with 3 retries
def log_temperature():
    print("Attempting to read sensor data...")
    filename = initialize_csv()

    temperature = None
    humidity = None

    for attempt in range(1, DHT_RETRIES + 1):
        try:
            temperature = dht_sensor.temperature
            humidity = dht_sensor.humidity

            if humidity is not None and temperature is not None:
                break  # Valid reading, exit loop

            print(f"Attempt {attempt}/{DHT_RETRIES}: Invalid sensor reading, retrying...")
            time.sleep(2)  # Wait before retrying
        except RuntimeError as error:
            print(f"Attempt {attempt}/{DHT_RETRIES}: Sensor error: {error}, retrying...")
            time.sleep(2)  # Wait before retrying

    if humidity is not None and temperature is not None:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        with open(filename, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([date_str, time_str, temperature, humidity])
        print(f"Logged: {date_str} {time_str} - Temp={temperature:.1f}°C, Humidity={humidity:.1f}% (CSV filename: {filename})")

        # Write to InfluxDB only if connection is active
        if influx_client:
            point = Point("temperature_humidity") \
                .tag("sensor", "DHT22") \
                .field("temperature", temperature) \
                .field("humidity", humidity) \
                .time(now)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
            print(f"Logged: {date_str} {time_str} - Temp={temperature:.1f}°C, Humidity={humidity:.1f}% (Sent to InfluxDB)")
        else:
            print(f"Logged: {date_str} {time_str} - Temp={temperature:.1f}°C, Humidity={humidity:.1f}% (InfluxDB not available)")
    else:
        print(f"Failed to retrieve valid data after {DHT_RETRIES} attempts.")

if __name__ == "__main__":
    print("Ensuring CSV file exists...")
    initialize_csv()  # Ensure CSV file exists at startup

    next_run_time = time.monotonic()  # Get precise start time
    print("Starting measurement loop...")

    try:
        while True:
            log_temperature()
            next_run_time += LOG_INTERVAL  # Schedule the next exact run time
            sleep_time = max(0, next_run_time - time.monotonic())  # Ensure we never sleep negative
            print(f"Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n Stopping logger...")
    # Ensure propper cleanup when exiting
    if influx_client:
        write_api.close()
        influx_client.close()
        print("InfluxDB connection closed.")
    print("Logger stopped")

