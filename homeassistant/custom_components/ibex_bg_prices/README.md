# IBEX BG Home Assistant Integration

This integration provides real-time electricity price data from the Bulgarian IBEX (Independent Bulgarian Energy Exchange) Day Ahead Market.

## Features

- **Current Price**: Most recent electricity price
- **Average Price**: Average price across all time periods
- **Min/Max Price**: Lowest and highest prices
- **Total Volume**: Total electricity volume traded

## Installation

1. Copy the `ibex_bg_prices` folder to your Home Assistant `custom_components` directory:
   ```
   <config>/custom_components/ibex_bg_prices/
   ```

2. Restart Home Assistant

3. Go to **Settings** > **Devices & Services** > **Add Integration**

4. Search for "IBEX BG" and add it

## Configuration

The integration requires no configuration - it will automatically fetch data from the IBEX API.

## Sensors

The integration creates the following sensors:

- `sensor.ibex_current_price` - Current electricity price (BGN/MWh)
- `sensor.ibex_average_price` - Average electricity price (BGN/MWh)
- `sensor.ibex_min_price` - Minimum electricity price (BGN/MWh)
- `sensor.ibex_max_price` - Maximum electricity price (BGN/MWh)
- `sensor.ibex_total_volume` - Total electricity volume (MWh)

## Data Update Frequency

The integration updates data every 5 minutes by default.

## Troubleshooting

If you encounter issues:

1. Check the Home Assistant logs for error messages
2. Ensure your Home Assistant instance has internet connectivity
3. Verify that the IBEX API is accessible

## Data Source

This integration fetches data from the IBEX Day Ahead Market API:
- URL: `https://ibex.bg/Ext/IDM_Homepage/fetch_dam.php`
- Language: Bulgarian (bg)
- Market: Day Ahead Market (num=73)
