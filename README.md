# Point Weather Forecast
Bias-corrected short-term weather forecast pipeline for New Delhi (VIDP).
Combines METAR observations with NWP model output to produce calibrated 7-day hourly forecasts.
## Variables
Temperature (°C), Relative Humidity (%)  and Wind Speed (m/s) variables are used from Open-Meteo (Forecast + Hindcast) + METAR (Observation). For Temperature and Relative Humidity, diurnal additive bias, and for Wind Speed, Quantile Mapping is used for Bias correction.
## Data Sources
- **Observations:** [Iowa State ASOS Network](https://mesonet.agron.iastate.edu/request/download.phtml) — Station VIDP (IGI Airport, New Delhi)
- **Forecast/Hindcast:** [Open-Meteo API](https://open-meteo.com/en/docs) — Hourly, past 7 days + 7-day forecast
## How to Run
### Install dependencies
pip install -r requirements.txt
### Run the pipeline
python ST_forecast_demo.py
## Output
Generates a 3-panel validation plot comparing actual observations,
raw forecast, and bias-calibrated forecast for all three variables.
