---
name: weather
type: read
side_effect: false
---
# weather

Fetch current weather information for a specified city using OpenWeather API.
Parameters:
- `city`: Name of the city (e.g. Hanoi, Ho Chi Minh, Tokyo, London).
- `units`: Measurement unit. Default is `"metric"` (Celsius). `"imperial"` for Fahrenheit.

Returns a dictionary containing city name, country, temperature, feels_like, humidity, weather description, wind speed, and status.
