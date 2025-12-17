import os
from glob import glob
import pandas as pd
import numpy as np
import csv
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from joblib import dump

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREFERRED_FILENAME = "live_air_quality.csv"
DATA_FILE = os.path.join(BASE_DIR, "air_quality_data.csv")


def find_best_csv(base_dir=BASE_DIR, preferred=PREFERRED_FILENAME):
    pref_path = os.path.join(base_dir, preferred)
    if os.path.exists(pref_path) and os.path.getsize(pref_path) > 0:
        return pref_path
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        return DATA_FILE
    csvs = glob(os.path.join(base_dir, "*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {base_dir}")
    non_empty = [(p, os.path.getsize(p)) for p in csvs if os.path.getsize(p) > 0]
    if not non_empty:
        raise ValueError(f"All CSV files in {base_dir} are empty. Files found: {csvs}")
    non_empty.sort(key=lambda t: t[1], reverse=True)
    return non_empty[0][0]


def _try_read(path):
    """
    Robust CSV reader with multiple tolerant fallbacks for malformed CSVs.
    Returns a pandas.DataFrame or raises RuntimeError with last exception.
    """
    attempts = [
        {"kwargs": {"encoding": "utf-8"}, "label": "utf-8 (default engine)"},
        {"kwargs": {"encoding": "utf-8-sig"}, "label": "utf-8-sig (BOM)"},
        {"kwargs": {"encoding": "latin1"}, "label": "latin1"},
        # python engine auto-sep (sniff)
        {"kwargs": {"engine": "python", "sep": None}, "label": "python engine, auto-sep"},
    ]

    last_exc = None
    for att in attempts:
        try:
            df = pd.read_csv(path, **att["kwargs"])
            if df is None or df.shape[1] == 0:
                raise pd.errors.EmptyDataError(f"No columns parsed (attempt: {att['label']})")
            print(f"[reader] Success with: {att['label']} -> columns={len(df.columns)} rows={len(df)}")
            return df
        except Exception as e:
            last_exc = e

    # Attempt: python engine and skip bad lines (requires pandas >= 1.3)
    try:
        df = pd.read_csv(path, engine="python", sep=None, on_bad_lines='skip', encoding="utf-8")
        if df is not None and df.shape[1] > 0:
            print("[reader] Succeeded with python engine + on_bad_lines='skip'")
            return df
    except Exception as e:
        last_exc = e

    # Attempt: QUOTE_NONE (useful when quotes are inconsistent). Need quoting from csv module.
    try:
        df = pd.read_csv(path, engine="python", sep=None, quotechar='"', quoting=csv.QUOTE_NONE, encoding="latin1", on_bad_lines='skip')
        if df is not None and df.shape[1] > 0:
            print("[reader] Succeeded with QUOTE_NONE fallback (latin1)")
            return df
    except Exception as e:
        last_exc = e

    # Last-resort: read the file line-by-line, detect modal column count, keep only well-formed rows
    try:
        print("[reader] Attempting modal-column-count cleaning (may be slower).")
        # Read first 2000 lines to determine modal separator and column count heuristically
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            sample_lines = [next(f) for _ in range(2000)]
    except StopIteration:
        # file shorter than 2000 lines, that's fine — use all read lines
        pass
    except Exception:
        sample_lines = None

    if sample_lines:
        # try both comma and semicolon to determine which gives consistent modal count
        def modal_count(lines, sep):
            counts = {}
            for ln in lines:
                counts.setdefault(len(ln.split(sep)), 0)
                counts[len(ln.split(sep))] += 1
            # return separator that produces highest modal count and its mode count
            mode = max(counts.items(), key=lambda kv: kv[1])
            return mode  # (col_count, frequency)

        comma_mode = modal_count(sample_lines, ",")
        semi_mode = modal_count(sample_lines, ";")

        # choose sep that gives higher modal frequency
        chosen_sep = "," if comma_mode[1] >= semi_mode[1] else ";"
        modal_cols = comma_mode[0] if chosen_sep == "," else semi_mode[0]

        # Now do a streaming read and keep only rows that match modal_cols
        cleaned_rows = []
        kept = 0
        total = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                total += 1
                cols = line.split(chosen_sep)
                if len(cols) == modal_cols:
                    cleaned_rows.append(line)
                    kept += 1
        if kept == 0:
            last_exc = RuntimeError("Modal-cleaner found 0 well-formed rows.")
        else:
            # create an in-memory CSV from cleaned_rows and read it
            from io import StringIO
            cleaned_csv = StringIO("".join(cleaned_rows))
            try:
                df = pd.read_csv(cleaned_csv, sep=chosen_sep)
                print(f"[reader] Modal-cleaner kept {kept}/{total} rows with sep='{chosen_sep}', cols={modal_cols}")
                if df.shape[1] == 0:
                    raise pd.errors.EmptyDataError("Modal-cleaner produced 0 columns.")
                return df
            except Exception as e:
                last_exc = e

    raise RuntimeError(f"Failed to parse file {path}. Last error: {last_exc}")


def load_data(path=None):
    if path is None:
        path = find_best_csv()

    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")
    if os.path.getsize(path) == 0:
        raise ValueError(f"Data file exists but is empty: {path}")

    print(f"[load_data] Using data file: {path} (size={os.path.getsize(path)} bytes)")
    df = _try_read(path)

    df.columns = [str(c).strip() for c in df.columns]

    candidates = [
        "pm25", "pm_25", "pm2_5", "pm2.5", "pm2_5(ug/m3)", "pm2.5(ug/m3)",
        "pm2_5_ug_m3", "pm25_ugm3", "pm2_5_ugm3", "pm_2_5", "pm25 (ug/m3)",
        "pm2.5_ugm3", "pm2_5_ug/m3"
    ]
    col_map = {col.lower(): col for col in df.columns}
    found_col = None
    for cand in candidates:
        if cand.lower() in col_map:
            found_col = col_map[cand.lower()]
            break

    if found_col is None:
        for col in df.columns:
            lc = col.lower()
            if "pm2" in lc or "pm 2" in lc or "pm2.5" in lc or lc.replace(".", "").replace("_", "").startswith("pm25"):
                found_col = col
                break

    if found_col is None:
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(numeric_cols) == 1:
            found_col = numeric_cols[0]
            print(f"[load_data] Warning: using the single numeric column '{found_col}' as pm25.")
        else:
            if "value" in col_map:
                found_col = col_map["value"]
            elif "measurement" in col_map:
                found_col = col_map["measurement"]

    if found_col is None:
        raise KeyError(
            "Could not detect a pm2.5 column automatically. "
            "Available columns: " + ", ".join(map(str, df.columns))
            + "\nPlease rename the pm2.5 column to one of: pm25, pm2_5, pm2.5, pm_25, etc."
        )

    series = df[found_col].copy()
    series = pd.to_numeric(series, errors="coerce")
    series = series.dropna()
    if series.empty:
        raise ValueError(f"No numeric values found in detected pm25 column '{found_col}' after coercion.")

    arr = series.values.reshape(-1, 1).astype(float)
    print(f"[load_data] Loaded {arr.shape[0]} rows from column '{found_col}'.")
    return arr


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
    data = load_data()  # auto-selects/cleans file
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(data)

    time_step = 10
    X, y = prepare_data(scaled_data, time_step)
    if X.size == 0:
        raise ValueError("Not enough data to create training sequences. Try a smaller time_step or provide more rows.")
    X = X.reshape(X.shape[0], X.shape[1], 1)

    model = build_model(time_step)
    model.fit(X, y, batch_size=16, epochs=10)

    model.save(os.path.join(BASE_DIR, "pm25_lstm_model.h5"))
    dump(scaler, os.path.join(BASE_DIR, "scaler.save"))
    print("✅ Model trained and saved as 'pm25_lstm_model.h5' (scaler saved as 'scaler.save')")


if __name__ == "__main__":
    train_model()
