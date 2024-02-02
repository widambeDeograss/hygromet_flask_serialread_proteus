import random
import threading
import re
from flask import Flask, jsonify
import serial
import psycopg2
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)
cors = CORS(app)
socketio = SocketIO(app)


# Function to extract and save Moisture data
def extract_and_save_rainfall(data, cursor):
    rainfall_match = re.search(r'Rainfall:([A-Za-z]+)', data)
    rainfall_status = rainfall_match.group(1).upper() if rainfall_match else None

    if rainfall_status is not None:
        cursor.execute("INSERT INTO rainfall_data (rain_status) VALUES (%s)", (rainfall_status,))
        print("Rainfall data saved - Status:", rainfall_status)


def extract_and_save_moisture(data, cursor):
    moisture_match = re.search(r'Moisture:(\d+\.\d+)', data)
    moisture_percentage = float(moisture_match.group(1)) if moisture_match else None
    print(moisture_percentage)

    if moisture_percentage is not None:
        cursor.execute("INSERT INTO moisture_data (moisture_percentage) VALUES (%s)", (moisture_percentage,))
        print("Moisture data saved:", moisture_percentage)


# Function to extract and save Water Level data
def extract_and_save_water_level(data, cursor):
    water_level_match = re.search(r'WaterLevel: ([A-Za-z]+)', data)
    water_level_status = water_level_match.group(1).upper() if water_level_match else None

    # Extract Water Level Distance
    distance_match = re.search(r'WaterLevelD:\s*(-?\d+)', data)
    water_level_distance = int(distance_match.group(1)) if distance_match else None
    print(water_level_status)
    if water_level_status is not None:
        cursor.execute("INSERT INTO water_level_data (status, distance) VALUES (%s, %s)", (water_level_status, water_level_distance))
        print("Water Level data saved - Status:", water_level_status, "Distance:", water_level_distance)


# Function to extract and save pH data
def extract_and_save_ph(data, cursor):
    ph_match = re.search(r'pH : (\d+\.\d+)', data)
    ph_level = float(ph_match.group(1)) if ph_match else None
    print("-------------------------")
    print(ph_level)

    if ph_level is not None:
        if ph_level > 7.9:
            ph_status = "HIGH"
            cursor.execute("INSERT INTO ph_data (ph_level, status) VALUES (%s, %s)", (ph_level, ph_status))
            print("pH data saved - Level:", ph_level, "Status:", ph_status)
        elif ph_level < 6.9:
            ph_status = "LOW"
            cursor.execute("INSERT INTO ph_data (ph_level, status) VALUES (%s, %s)", (ph_level, ph_status))
            print("pH data saved - Level:", ph_level, "Status:", ph_status)
        else:
            ph_status = "MODERATE"
            cursor.execute("INSERT INTO ph_data (ph_level, status) VALUES (%s, %s)", (ph_level, ph_status))
            print("pH data saved - Level:", ph_level, "Status:", ph_status)


# Function to extract and save Flow Rate data
def extract_and_save_flow_rate(data, cursor):
    # flow_rate_match = re.search(r'FlowRate: (\d+)', data)
    # flow_rate = int(flow_rate_match.group(1)) if flow_rate_match else None
    #
    # volume_match = re.search(r'Volume:\s*(-?\d+\.\d+)', data)
    # flow_rate_volume = float(volume_match.group(1)) if volume_match else None

    flow_rate = random.uniform(0, 100)

    # Generate random flow rate volume (between -100 and 100)
    flow_rate_volume = random.uniform(-100, 100)


    if flow_rate is not None:
        cursor.execute("INSERT INTO flow_rate_data (flow_rate, volume) VALUES (%s, %s)", (flow_rate, flow_rate_volume))
        print("Flow Rate data saved - Rate:", flow_rate, "Volume:", flow_rate_volume)


conn = psycopg2.connect(database="hydromet", user="postgres", password="post30", host="localhost", port="5432")
cursor = conn.cursor()

ser = serial.Serial('COM2', 9600)  # Replace 'COMx' with the port where Proteus is sending data


def read_serial_data():
    while True:
        data = ser.readline().decode().strip()

        # Extract and process hydromet data from the received message
        extract_and_save_ph(data, cursor)
        extract_and_save_moisture(data, cursor)
        extract_and_save_water_level(data, cursor)
        extract_and_save_flow_rate(data, cursor)
        extract_and_save_rainfall(data, cursor)
        # Commit the changes to the database
        conn.commit()


# Start the serial reading thread when the Flask app starts
serial_thread = threading.Thread(target=read_serial_data)
serial_thread.start()

@app.route('/api/latest_data', methods=['GET'])
def get_latest_data():
    cursor.execute("SELECT * FROM moisture_data ORDER BY timestamp DESC LIMIT 1")
    moisture_data = cursor.fetchone()

    cursor.execute("SELECT * FROM water_level_data ORDER BY timestamp DESC LIMIT 1")
    water_level_data = cursor.fetchone()

    cursor.execute("SELECT * FROM ph_data ORDER BY timestamp DESC LIMIT 1")
    ph_data = cursor.fetchone()

    cursor.execute("SELECT * FROM flow_rate_data ORDER BY timestamp DESC LIMIT 20")
    flow_rate_data_list = cursor.fetchall()


    cursor.execute("SELECT * FROM rainfall_data ORDER BY timestamp DESC LIMIT 1")
    rain_data = cursor.fetchone()
    top_20_flow_rate_data = []
    if flow_rate_data_list:
        for entry in flow_rate_data_list:
            flow_rate_entry = {
                'flow_rate': entry[0],
                'volume': entry[1],
                'timestamp': entry[2] # Assuming timestamp is a datetime column
            }
            top_20_flow_rate_data.append(flow_rate_entry)

    latest_data = {
        'moisture_data': moisture_data,
        'water_level_data': water_level_data,
        'ph_data': ph_data,
        'flow_rate_data': top_20_flow_rate_data,
        'rain_fall': rain_data
    }

    return jsonify(latest_data)

def send_data():
    while True:
        socketio.emit('update_data', get_latest_data())
        socketio.sleep(5)  # Update every 5 seconds (adjust as needed)


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    socketio.start_background_task(target=send_data)


if __name__ == "__main__":
    app.run(host="192.168.74.123", port=5000, debug=True)

