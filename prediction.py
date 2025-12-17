import numpy as np
from tensorflow.keras.models import load_model
from joblib import load
from sds011_reader import SDS011
import time

MODEL_FILE = "pm25_lstm_model.h5"
SCALER_FILE = "scaler.save"

def predict_pm25():
    model = load_model(MODEL_FILE)
    scaler = load(SCALER_FILE)
    sensor = SDS011(port="COM3")  # Change COM port if needed

    data_window = []

    print("🔮 Real-time PM2.5 Prediction Started...")

    while True:
        pm25, _ = sensor.read()
        data_window.append(pm25)

        if len(data_window) > 10:
            data_window.pop(0)

        if len(data_window) == 10:
            input_data = np.array(data_window).reshape(-1, 1)
            scaled_input = scaler.transform(input_data)
            scaled_input = np.reshape(scaled_input, (1, 10, 1))

            predicted_scaled = model.predict(scaled_input)
            predicted_pm25 = scaler.inverse_transform(predicted_scaled)

            print(f"Measured PM2.5: {pm25:.2f} | Predicted Next PM2.5: {predicted_pm25[0][0]:.2f}")

        time.sleep(3)

if __name__ == "__main__":
    predict_pm25()
