#!/usr/bin/env python
# coding: utf-8



# !pip install openmeteo-requests
# !pip install requests-cache retry-requests

import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import numpy as np
import matplotlib.pyplot as plt
import requests
from datetime import datetime, timedelta, timezone
from io import StringIO

                                                    ### METAR Data Fetch ###
    
STATION  = "VIDP" ## Station Code for IGI airport New Delhi
NETWORK  = "IN__ASOS"
VARIABLES = ["tmpc", "relh", "sped"]
BASE_URL  = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

end_dt   = datetime.now(timezone.utc)
start_dt = end_dt - timedelta(days=7)

params = {
    "network"     : NETWORK,
    "station"     : STATION,
    "data"        : VARIABLES,
    "year1"       : start_dt.year,
    "month1"      : start_dt.month,
    "day1"        : start_dt.day,
    "year2"       : end_dt.year,
    "month2"      : end_dt.month,
    "day2"        : end_dt.day,
    "tz"          : "Etc/UTC",
    "format"      : "onlycomma",
    "latlon"      : "no",
    "elev"        : "no",
    "missing"     : "M",
    "trace"       : "T",
    "direct"      : "no",
    "report_type" : [3, 4],
}

print(f"Fetching METAR data for {STATION}  |  {start_dt.date()} → {end_dt.date()} UTC")

response = requests.get(BASE_URL, params=params, timeout=60)
response.raise_for_status()

raw_text = response.text
lines = raw_text.splitlines()
csv_start = next(
    (i for i, line in enumerate(lines) if line.strip().lower().startswith("station")),
    0,
)
csv_text = "\n".join(lines[csv_start:])
actual = pd.read_csv(StringIO(csv_text), na_values=["M", ""])  # "M" → NaN

actual.rename(
    columns={
        "station" : "station",
        "valid"   : "datetime"},
    inplace=True,
)

actual["datetime"] = pd.to_datetime(actual["datetime"], utc=True)
keep_cols = ["datetime", "station", "tmpc", "relh", "sped"]
actual = actual[keep_cols].copy()
actual['datetime_ist'] = (
    pd.to_datetime(actual['datetime'])
      .dt.tz_convert('Asia/Kolkata')
      .dt.tz_localize(None)
)

actual.sort_values("datetime_ist", inplace=True)
actual.reset_index(drop=True, inplace=True)

print(f"Rows fetched : {len(actual)}")
print(f"  Period       : {actual['datetime'].min()} → {actual['datetime'].max()}")
print(actual.head().to_string(index=False))

# out_file = f"D:/Assignment/metar_{STATION}_{start_dt.date()}_to_{end_dt.date()}.csv"
# actual.to_csv(out_file, index=False)
# print(f"\nData saved to: {out_file}")

                                                ### Forecast Fetch ###

cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo    = openmeteo_requests.Client(session=retry_session)

#### Location - New Delhi ####
LATITUDE  = 28.6139
LONGITUDE = 77.2090

params = {
    "latitude":LATITUDE,
    "longitude":LONGITUDE,
    "hourly": ["wind_speed_10m", "temperature_2m", "relative_humidity_2m"],
    "wind_speed_unit": "ms",
    "timezone":"Asia/Kolkata",
    "past_days":7,          
    "forecast_days":7,
}



responses = openmeteo.weather_api("https://api.open-meteo.com/v1/forecast", params=params)
response  = responses[0]

print(f"  Lat / Lon  : {response.Latitude():.4f}°N  {response.Longitude():.4f}°E")
print(f"  Elevation  : {response.Elevation():.0f} m asl")
print(f"  UTC offset : {response.UtcOffsetSeconds() // 3600:+d} h  ({response.UtcOffsetSeconds()} s)")

hourly = response.Hourly()

date_index = pd.date_range(
    start=pd.to_datetime(hourly.Time(),    unit="s", utc=True),
    end  =pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
    freq =pd.Timedelta(seconds=hourly.Interval()),
    inclusive="left",
).tz_convert("Asia/Kolkata")

VARIABLES = [
    "wind_speed_10m",
    "temperature_2m",
    "relative_humidity_2m",  
]

hourly_data = {"datetime_ist": date_index}
for i, var in enumerate(VARIABLES):
    hourly_data[var] = hourly.Variables(i).ValuesAsNumpy()

df = pd.DataFrame(hourly_data).set_index("datetime_ist")

now       = pd.Timestamp.now(tz="Asia/Kolkata")
df_past   = df[df.index <= now].copy()
df_future = df[df.index  > now].copy()


df["split"] = "hindcast"
df.loc[df.index > now, "split"] = "forecast"

print(f"\nTotal rows fetched : {len(df)}")
print(f"  Hindcast (past 2d): {len(df_past)} rows  "
      f"[{df_past.index[0]}  →  {df_past.index[-1]}]")
print(f"  Forecast (next 7d): {len(df_future)} rows  "
      f"[{df_future.index[0]}  →  {df_future.index[-1]}]")

print("\nHindcast tail (last 6 h before now)")
print(df_past.tail(6)[["temperature_2m", "relative_humidity_2m",
                        "wind_speed_10m"]].to_string())

print("\nForecast head (next 12 h)")
print(df_future.head(12)[["temperature_2m", "relative_humidity_2m",
                           "wind_speed_10m"]].to_string())

# OUT = "D:/Assignment/forecast_delhi.csv"
# df.to_csv(OUT)

                                                    ### Bias Mapping ###

df = df.reset_index()
df['datetime_ist'] = df['datetime_ist'].dt.tz_localize(None)
df['datetime_ist'] = pd.to_datetime(df['datetime_ist'])
actual['datetime_ist'] = pd.to_datetime(actual['datetime_ist'])
actual['sped_ms'] = actual['sped'] * 0.44704 ### Actual winds from mph to m/sec

merged = pd.merge(
    df,
    actual[['datetime_ist', 'tmpc', 'relh', 'sped_ms']].set_index('datetime_ist').resample('H').mean(),
    on='datetime_ist',
    how='left'
)

merged['hour'] = merged['datetime_ist'].dt.hour
df['hour'] = df['datetime_ist'].dt.hour

### Temperature Bias Mapping ###
train = merged[(merged['split'] == 'hindcast') & (~merged['tmpc'].isna())].copy()
train['temp_bias'] = (train['tmpc'] - train['temperature_2m'])
hourly_temp_bias = (train.groupby('hour')['temp_bias'].mean())

### Relative Humidity Bias ###
train['rh_bias'] = (train['relh'] - train['relative_humidity_2m'])
hourly_rh_bias = (train.groupby('hour')['rh_bias'].mean())

### Wind Bias ###
wind_train = train[(~train['wind_speed_10m'].isna()) & (~train['sped_ms'].isna())].copy()
fcst_ws = wind_train['wind_speed_10m'].values
obs_ws = wind_train['sped_ms'].values
fcst_sorted = np.sort(fcst_ws)
obs_sorted = np.sort(obs_ws)
p = np.linspace(0, 1, len(fcst_sorted))

df['temp_hourly_bias'] = (df['hour'].map(hourly_temp_bias))
df['temperature_calibrated'] = (df['temperature_2m'] + df['temp_hourly_bias'])

df['rh_hourly_bias'] = (df['hour'].map(hourly_rh_bias))
df['rh_calibrated'] = (df['relative_humidity_2m'] + df['rh_hourly_bias'])
df['rh_calibrated'] = (df['rh_calibrated'].clip(0, 100))

forecast_percentiles = np.interp(df['wind_speed_10m'],fcst_sorted,p)
df['windspeed_calibrated_ms'] = np.interp(forecast_percentiles,p,obs_sorted)
df['windspeed_calibrated_ms'] = (df['windspeed_calibrated_ms'].clip(lower=0))
df['windspeed_calibrated_ms'] = (df['windspeed_calibrated_ms'].rolling(3, center=True, min_periods=1).mean())

### Final Dataframe ###
corrected_forecast = df[
    [
        'datetime_ist',
        'temperature_2m',
        'relative_humidity_2m',
        'wind_speed_10m',
        'temperature_calibrated',
        'rh_calibrated',
        'windspeed_calibrated_ms',
        'split'
    ]
].copy()

print(corrected_forecast.head())

                                                ### Validation ###

fig, axes = plt.subplots(3, 1, figsize=(18, 16), sharex=True)
fig.suptitle('Forecast Calibration — New Delhi', fontsize=16, fontweight='bold', y=1.01)

forecast_start = corrected_forecast[corrected_forecast['split'] == 'forecast']['datetime_ist'].min()

plot_cfg = [
    {
        "ax"    : axes[0],
        "lines" : [
            (merged['datetime_ist'],merged['tmpc'],'Actual Temperature',  None),
            (corrected_forecast['datetime_ist'],corrected_forecast['temperature_2m'],'Raw Forecast',None),
            (corrected_forecast['datetime_ist'],corrected_forecast['temperature_calibrated'],'Calibrated Forecast', None),
        ],
        "ylabel": "Temperature (°C)",
        "title" : "Temperature Calibration",
    },
    {
        "ax"    : axes[1],
        "lines" : [
            (merged['datetime_ist'], merged['relh'],'Actual RH',None),
            (df['datetime_ist'],df['relative_humidity_2m'],'Raw Forecast RH', None),
            (df['datetime_ist'],df['rh_calibrated'],'Calibrated RH',None),
        ],
        "ylabel": "Relative Humidity (%)",
        "title" : "Relative Humidity Calibration",
    },
    {
        "ax"    : axes[2],
        "lines" : [
            (merged['datetime_ist'], merged['sped_ms'],'Actual Wind Speed',None),
            (df['datetime_ist'],df['wind_speed_10m'],'Raw Forecast Wind Speed', None),
            (df['datetime_ist'],df['windspeed_calibrated_ms'],'Calibrated Wind Speed',None),
        ],
        "ylabel": "Wind Speed (m/s)",
        "title" : "Wind Speed Calibration",
    },
]

for cfg in plot_cfg:
    ax = cfg["ax"]
    for x, y, label, color in cfg["lines"]:
        ax.plot(x, y, label=label, linewidth=2, **({"color": color} if color else {}))
    ax.axvline(forecast_start, linestyle='--', linewidth=2, color='black', label='Forecast Start')
    ax.set_ylabel(cfg["ylabel"], fontsize=11)
    ax.set_title(cfg["title"], fontsize=12)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.4)

axes[2].set_xlabel('Datetime (IST)', fontsize=11)
fig.autofmt_xdate(rotation=30)
plt.tight_layout()
#plt.savefig('D:/Assignment/Forecast_Calibration_subplots.png', dpi=150, bbox_inches='tight')
plt.show()




