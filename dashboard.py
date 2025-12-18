# live_dashboard.py
import time
import threading
from collections import deque
import os
import csv

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS

from sds011_reader import SDS011
# Optional model imports
try:
    from tensorflow.keras.models import load_model
    from joblib import load as joblib_load
    MODEL_AVAILABLE = True
except Exception:
    MODEL_AVAILABLE = False

# ---------------- CONFIG ----------------
PORT = "COM3"           # Your sensor COM port
READ_INTERVAL = 2        # seconds between reads
WINDOW_SIZE = 30        # number of points for dashboard graph
CSV_FILE = "live_air_quality.csv"  # auto-save file
# --------------------------------------

app = Flask(__name__)
CORS(app)

# in-memory buffers
pm25_buf = deque(maxlen=WINDOW_SIZE)
pm10_buf = deque(maxlen=WINDOW_SIZE)
ts_buf = deque(maxlen=WINDOW_SIZE)
latest = {"pm25": None, "pm10": None, "timestamp": None, "predicted_pm25": None}

# Load model & scaler if available
model = None
scaler = None
if MODEL_AVAILABLE:
    try:
        if os.path.exists("pm25_lstm_model.h5") and os.path.exists("scaler.save"):
            model = load_model("pm25_lstm_model.h5")
            scaler = joblib_load("scaler.save")
            print("✅ Prediction model and scaler loaded.")
        else:
            print("⚠️ Model or scaler files not found — predictions disabled.")
    except Exception as e:
        print("⚠️ Error loading model/scaler:", e)

# Create CSV with headers if doesn't exist
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "pm25", "pm10", "predicted_pm25"])

# ---------------- SENSOR THREAD ----------------
def sensor_loop():
    sensor = SDS011(port=PORT)
    try:
        while True:
            pm25, pm10 = sensor.read()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            if pm25 is None:
                time.sleep(1)
                continue
            pm25_buf.append(float(pm25))
            pm10_buf.append(float(pm10))
            ts_buf.append(timestamp)
            latest["pm25"] = float(pm25)
            latest["pm10"] = float(pm10)
            latest["timestamp"] = timestamp

            # Prediction
            if model is not None and scaler is not None and len(pm25_buf) >= model.input_shape[1]:
                import numpy as np
                window = list(pm25_buf)[-model.input_shape[1]:]
                arr = np.array(window).reshape(-1,1)
                try:
                    scaled = scaler.transform(arr)
                    scaled = scaled.reshape(1, scaled.shape[0],1)
                    pred_scaled = model.predict(scaled, verbose=0)
                    pred = scaler.inverse_transform(pred_scaled)[0][0]
                    latest["predicted_pm25"] = float(pred)
                except Exception:
                    latest["predicted_pm25"] = None
            else:
                latest["predicted_pm25"] = None

            # Save to CSV
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, pm25, pm10, latest["predicted_pm25"]
                ])

            time.sleep(READ_INTERVAL)
    except Exception as e:
        print("Sensor loop error:", e)
    finally:
        sensor.close()

# ---------------- FLASK API ----------------
@app.route("/api/live")
def api_live():
    return jsonify({
        "latest": latest,
        "history": {
            "timestamps": list(ts_buf),
            "pm25": list(pm25_buf),
            "pm10": list(pm10_buf)
        }
    })

# ---------------- DASHBOARD HTML ----------------
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>DeepAir — Live Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    .card { padding: 12px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); margin-bottom: 16px; }
    #values { display:flex; gap:20px; align-items:center; }
    .val { font-size: 1.4rem; padding:4px 8px; border-radius:4px; }
  </style>
</head>
<body>
  <h2>DEEPAIR — Real-time Sensor Dashboard</h2>
  <div class="card" id="values">
    <div>Measured PM2.5: <span id="pm25" class="val">—</span> µg/m³</div>
    <div>Measured PM10: <span id="pm10" class="val">—</span> µg/m³</div>
    <div>Predicted Next PM2.5: <span id="pred" class="val">—</span> µg/m³</div>
    <div>Last Update: <span id="last" class="val">—</span></div>
  </div>

  <div class="card">
    <canvas id="chart" height="120"></canvas>
  </div>

<script>
const ctx = document.getElementById('chart').getContext('2d');
let chart;

function getColorPM25(value){
  if(value <= 12) return 'green';
  if(value <= 35) return 'yellow';
  if(value <= 55) return 'orange';
  if(value <= 150) return 'red';
  return 'purple';
}

function getColorPM10(value){
  if(value <= 54) return 'green';
  if(value <= 154) return 'yellow';
  if(value <= 254) return 'orange';
  if(value <= 354) return 'red';
  return 'purple';
}

async function fetchLive(){
  try{
    const res = await fetch('http://localhost:5000/api/live');
    const data = await res.json();
    const hist = data.history;

    const pm25_val = data.latest.pm25 !== null ? data.latest.pm25.toFixed(2) : "—";
    const pm10_val = data.latest.pm10 !== null ? data.latest.pm10.toFixed(2) : "—";
    const pred_val = data.latest.predicted_pm25 !== null ? data.latest.predicted_pm25.toFixed(2) : "—";

    document.getElementById('pm25').innerText = pm25_val;
    document.getElementById('pm10').innerText = pm10_val;
    document.getElementById('pred').innerText = pred_val;
    document.getElementById('last').innerText = data.latest.timestamp || "—";

    // set background colors
    document.getElementById('pm25').style.backgroundColor = pm25_val !== "—" ? getColorPM25(parseFloat(pm25_val)) : 'transparent';
    document.getElementById('pm10').style.backgroundColor = pm10_val !== "—" ? getColorPM10(parseFloat(pm10_val)) : 'transparent';
    document.getElementById('pm25').style.color = 'white';
    document.getElementById('pm10').style.color = 'white';

    const labels = hist.timestamps.length ? hist.timestamps : [];
    const pm25 = hist.pm25.length ? hist.pm25 : [];
    const pm10 = hist.pm10.length ? hist.pm10 : [];

    if(!chart){
      chart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            { label: 'PM2.5', data: pm25, fill: false, borderColor: 'red', tension: 0.2 },
            { label: 'PM10', data: pm10, fill: false, borderColor: 'blue', tension: 0.2 }
          ]
        },
        options: { responsive: true, scales: { y: { beginAtZero: true } } }
      });
    } else {
      chart.data.labels = labels;
      chart.data.datasets[0].data = pm25;
      chart.data.datasets[1].data = pm10;
      chart.update();
    }
  } catch(e){ console.error("fetch error", e); }
}

setInterval(fetchLive, 2000);
fetchLive();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

# ---------------- RUN ----------------
if __name__ == "__main__":
    t = threading.Thread(target=sensor_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
