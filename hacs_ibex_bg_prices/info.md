# IBEX BG

![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
![maintenance](https://img.shields.io/badge/maintainer-YourUsername-blue.svg)

Real-time electricity price data from the Bulgarian IBEX (Independent Bulgarian Energy Exchange) Day Ahead Market.

## Features

- **Current Price**: Most recent electricity price
- **Average Price**: Average price across all time periods
- **Min/Max Price**: Lowest and highest prices
- **Total Volume**: Total electricity volume traded
- **Auto-updates**: Data refreshes every 5 minutes
- **No configuration required**: Works out of the box

## Installation

1. Install via HACS (this repository)
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "IBEX BG" and add it

## Sensors

The integration creates 5 sensors:

- `sensor.ibex_current_price` - Current electricity price (BGN/MWh)
- `sensor.ibex_average_price` - Average electricity price (BGN/MWh)  
- `sensor.ibex_min_price` - Minimum electricity price (BGN/MWh)
- `sensor.ibex_max_price` - Maximum electricity price (BGN/MWh)
- `sensor.ibex_total_volume` - Total electricity volume (MWh)

## Usage

Perfect for:
- Monitoring electricity market prices
- Creating price-based automations
- Building energy cost dashboards
- Setting up price alerts

## Data Source

Fetches real-time data from the official IBEX Day Ahead Market API.

## Requirements

- Home Assistant 2023.1.0 or higher
- Internet connection
