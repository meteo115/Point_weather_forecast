# Point_weather_forecast
The code "ST_forecast_demo.py" performs 3 separate operations. 
First part of the code fetches the Metar data set from last 7 days to the current date. 
The second part takes point based hourly weather forceast + hindcast from [https://open-meteo.com/en/docs](Open Meteo). 
The next part calibrates the forceast using hourly Bias mapping for Temperature and Relative humidity, and using Quantile Mapping for wind speed and crates one calibrated hourly forecast till the next 7 days.
The plotting function provides a visual validation of the whole calibration process and compares the raw forecast and the calibrated forecast.
