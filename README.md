# DEEPAIR - Full Project

## Quick start (Windows - VS Code)

1. Create virtual env:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Edit `sds011_reader.py` port if required (currently set to COM3).

4. Start logger (creates `air_quality_data.csv`):
   ```
   python data_logger.py
   ```

5. Train model (requires collected PM2.5 data):
   ```
   python model_training.py
   ```

6. Predict next value:
   ```
   python prediction.py
   ```

7. Interpolate (requires `air_quality_data_with_coords.csv` with lat,lon,pm25):
   ```
   python interpolation.py
   ```

8. Run dashboard:
   ```
   python dashboard.py
   ```

## Notes
- Python: 3.8.10 (as you specified)
- COM port: COM3
- This zip is prepared for development and learning. Tweak parameters for production use.
