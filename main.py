import requests
import json
from datetime import datetime

# URL of the API endpoint
url = "https://ibex.bg/Ext/IDM_Homepage/fetch_dam.php?lang=bg&num=73"

# Headers to mimic a browser request (based on the curl command)
headers = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://ibex.bg/",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
}

# Cookies from the curl command
cookies = {
    "__wpdm_client": "fe1f4c32205edf6d6f93d2d060e8bcbd",
    "_ga": "GA1.1.1071599757.1759405313",
    "pll_language": "bg",
    "_ga_5LBFZ1MK81": "GS2.1.s1759453610$o2$g1$t1759453626$j44$l0$h0"
}

def fetch_ibex_bg_prices():
    """Fetch IBEX BG price data from the API endpoint"""
    try:
        # Send a GET request to the API
        response = requests.get(url, headers=headers, cookies=cookies)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            
            print(f"Successfully fetched {len(data)} price records")
            print("=" * 60)
            
            # Display the data in a formatted way
            for i, record in enumerate(data):
                date_str = record["date"]
                price = record["price"]
                volume = record["volume"]
                
                # Parse the date for better formatting
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                except:
                    formatted_date = date_str
                
                print(f"Record {i+1:2d}: {formatted_date} | Price: {price:8.2f} | Volume: {volume:8.1f}")
            
            return data
            
        else:
            print(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def save_to_json(data, filename="ibex_bg_prices.json"):
    """Save the price data to a JSON file"""
    if data:
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\nData saved to {filename}")
        except Exception as e:
            print(f"Error saving to file: {e}")

if __name__ == "__main__":
    print("Fetching IBEX BG price data...")
    price_data = fetch_ibex_bg_prices()
    
    if price_data:
        # Optionally save to file
        save_to_json(price_data)
        
        # Calculate some basic statistics
        if price_data:
            prices = [record["price"] for record in price_data]
            volumes = [record["volume"] for record in price_data]
            
            print("\n" + "=" * 60)
            print("SUMMARY STATISTICS:")
            print(f"Total records: {len(price_data)}")
            print(f"Price range: {min(prices):.2f} - {max(prices):.2f}")
            print(f"Average price: {sum(prices)/len(prices):.2f}")
            print(f"Total volume: {sum(volumes):.1f}")
            print(f"Average volume: {sum(volumes)/len(volumes):.1f}")