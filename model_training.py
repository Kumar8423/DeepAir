import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from joblib import dump

DATA_FILE = "air_quality_data.csv"

def load_data():
    df = pd.read_csv(DATA_FILE)
    df["pm25"] = df["pm25"].astype(float)
    return df["pm25"].values.reshape(-1, 1)

def prepare_data(data, time_step=10):
    X, y = [], []
    for i in range(len(data) - time_step - 1):
        X.append(data[i:(i + time_step), 0])
        y.append(data[i + time_step, 0])
    return np.array(X), np.array(y)

def build_model(input_shape):
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(input_shape, 1)),
        LSTM(50, return_sequences=False),
        Dense(25),
        Dense(1)
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model

def train_model():
    data = load_data()
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)

    time_step = 10
    X, y = prepare_data(scaled_data, time_step)
    X = X.reshape(X.shape[0], X.shape[1], 1)

    model = build_model(time_step)
    model.fit(X, y, batch_size=16, epochs=10)

    model.save("pm25_lstm_model.h5")
    dump(scaler, "scaler.save")
    print("✅ Model trained and saved as 'pm25_lstm_model.h5'")

if __name__ == "__main__":
    train_model()
