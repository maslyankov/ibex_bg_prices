# IBEX BG

A Python script and Home Assistant integration for fetching real-time electricity price data from the Bulgarian IBEX (Independent Bulgarian Energy Exchange) Day Ahead Market.

## 📊 What is IBEX?

IBEX is the Independent Bulgarian Energy Exchange, which operates the day-ahead electricity market in Bulgaria. This project provides easy access to real-time electricity prices through both a standalone Python script and a Home Assistant integration.

## 🚀 Features

- **Real-time Data**: Fetch current electricity prices from IBEX API
- **Multiple Formats**: Python script and Home Assistant integration
- **No Authentication**: Direct API access without login requirements
- **Comprehensive Data**: Current, average, min/max prices and total volume
- **Auto-updates**: Home Assistant integration updates every 5 minutes

## 📁 Project Structure

```
ibex_bg_prices/
├── main.py                           # Standalone Python script
├── requirements.txt                  # Python dependencies
├── homeassistant/                    # Home Assistant integration (manual install)
│   └── custom_components/
│       └── ibex_bg_prices/
└── hacs_ibex_bg_prices/              # HACS-ready integration package
    ├── hacs.json
    ├── info.md
    └── ibex_bg_prices/
```

## 🐍 Python Script Usage

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/maslyankov/ibex_bg_prices.git
   cd ibex_bg_prices
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Script

```bash
python main.py
```

### Sample Output

```
Fetching IBEX BG price data...
Successfully fetched 96 price records
============================================================
Record  1: 2025-10-03 00:00 | Price:   184.18 | Volume:  3631.5
Record  2: 2025-10-03 00:15 | Price:   167.22 | Volume:  3551.1
Record  3: 2025-10-03 00:30 | Price:   157.42 | Volume:  3002.6
...

Data saved to ibex_bg_prices.json

============================================================
SUMMARY STATISTICS:
Total records: 96
Price range: 120.50 - 250.75
Average price: 185.42
Total volume: 125000.0
Average volume: 1302.1
```

### Script Features

- **Formatted Output**: Clean table display of all price records
- **JSON Export**: Saves data to `ibex_bg_prices.json`
- **Statistics**: Calculates price range, averages, and totals
- **Error Handling**: Graceful handling of network and API errors

## 🏠 Home Assistant Integration

### Installation via HACS (Recommended)

1. **Add Custom Repository**:
   - Go to HACS → Integrations → Custom Repositories
   - Add: `https://github.com/maslyankov/ibex_bg_prices`
   - Category: Integration

2. **Install**:
   - Search for "IBEX BG" in HACS
   - Click Install

3. **Setup**:
   - Restart Home Assistant
   - Go to Settings → Devices & Services → Add Integration
   - Search for "IBEX BG" and add it

### Manual Installation

1. **Copy Integration**:
   ```bash
   cp -r homeassistant/custom_components/ibex_bg_prices /config/custom_components/
   ```

2. **Restart Home Assistant**

3. **Add Integration**:
   - Settings → Devices & Services → Add Integration
   - Search for "IBEX BG"

### Home Assistant Sensors

The integration creates 5 sensors:

| Sensor | Entity ID | Description | Unit |
|--------|-----------|-------------|------|
| Current Price | `sensor.ibex_current_price` | Most recent price | BGN/MWh |
| Average Price | `sensor.ibex_average_price` | Average across all periods | BGN/MWh |
| Min Price | `sensor.ibex_min_price` | Lowest price | BGN/MWh |
| Max Price | `sensor.ibex_max_price` | Highest price | BGN/MWh |
| Total Volume | `sensor.ibex_total_volume` | Total electricity volume | MWh |

### Usage Examples

#### Dashboard Card
```yaml
type: entities
title: IBEX Electricity Prices
entities:
  - entity: sensor.ibex_current_price
    name: Current Price
  - entity: sensor.ibex_average_price
    name: Average Price
  - entity: sensor.ibex_min_price
    name: Min Price
  - entity: sensor.ibex_max_price
    name: Max Price
  - entity: sensor.ibex_total_volume
    name: Total Volume
```

#### Price Alert Automation
```yaml
alias: "High Electricity Price Alert"
description: "Notify when electricity price exceeds 200 BGN/MWh"
trigger:
  - platform: numeric_state
    entity_id: sensor.ibex_current_price
    above: 200
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "High Electricity Price"
      message: "Current price: {{ states('sensor.ibex_current_price') }} BGN/MWh"
```

#### Energy Cost Calculation
```yaml
# Template sensor to calculate daily cost
template:
  - sensor:
      - name: "Daily Electricity Cost"
        unit_of_measurement: "BGN"
        state: >
          {% set current_price = states('sensor.ibex_current_price') | float(0) %}
          {% set daily_consumption = 10 %}  # kWh per day
          {{ (current_price * daily_consumption / 1000) | round(2) }}
```

## 🔧 Technical Details

### API Endpoint
- **URL**: `https://ibex.bg/Ext/IDM_Homepage/fetch_dam.php`
- **Parameters**: `lang=bg&num=73`
- **Method**: GET
- **Response**: JSON array of price records

### Data Format
```json
[
  {
    "date": "2025-10-03 00:00:00",
    "price": 184.1805110999999897103407420217990875244140625,
    "volume": 3631.5
  }
]
```

### Update Frequency
- **Python Script**: On-demand (when executed)
- **Home Assistant**: Every 5 minutes automatically

## 🛠️ Development

### Requirements
- Python 3.8+
- Home Assistant 2023.1.0+ (for integration)
- Internet connection

### Dependencies
- `requests` (Python script)
- `aiohttp` (Home Assistant integration)

### Testing the API
You can test the API directly with curl:
```bash
curl 'https://ibex.bg/Ext/IDM_Homepage/fetch_dam.php?lang=bg&num=73' \
  -H 'accept: */*' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
```

## 📈 Use Cases

- **Energy Monitoring**: Track electricity market prices
- **Cost Optimization**: Time energy usage based on price
- **Automation**: Trigger actions based on price thresholds
- **Analytics**: Historical price analysis
- **Dashboards**: Real-time price displays

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This project is not affiliated with IBEX. The data is fetched from publicly available APIs. Use at your own risk and ensure compliance with IBEX's terms of service.

## 🔗 Links

- [IBEX Official Website](https://ibex.bg/)
- [Home Assistant](https://www.home-assistant.io/)
- [HACS](https://hacs.xyz/)

## 📞 Support

If you encounter any issues:
1. Check the troubleshooting section in the Home Assistant integration README
2. Verify your internet connection
3. Check Home Assistant logs for error messages
4. Open an issue on GitHub

---

**Made with ❤️ for the Bulgarian energy community**
