import urllib.request
import json
import time

def fetch_and_ingest():
    print("[*] Fetching real-time global earthquake data from USGS...")
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AEGIS-CAD/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"[!] Failed to fetch USGS data: {e}")
        return

    features = data.get("features", [])
    print(f"[*] Found {len(features)} earthquakes > 4.5 Mag in the last 24 hours.")
    
    # We'll ingest the top 5 most recent ones to avoid flooding the demo
    for feature in features[:5]:
        props = feature["properties"]
        geom = feature["geometry"]
        
        place = props.get("place", "Unknown Location")
        mag = props.get("mag", 0)
        lng, lat, depth = geom.get("coordinates", [0, 0, 0])
        
        # Construct a realistic distress signal representing this real event
        raw_text = f"URGENT: Massive magnitude {mag} earthquake just struck {place}! Buildings are heavily damaged and we are trapped under rubble. Send rescue teams immediately!"
        
        payload = {
            "rawText": raw_text,
            "source": "USGS_AUTOMATED_SIMULATION",
            "lat": lat,
            "lng": lng,
            "senderContact": "+1-800-USGS-EQ"
        }
        
        print(f"[-] Pushing real event to AEGIS-CAD: {place} (Mag {mag})")
        
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/ingest/live",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req)
            print("    -> Successfully ingested.")
        except Exception as e:
            print(f"    -> Failed to push: {e}")
            
        time.sleep(1.5) # Slight delay for dramatic effect in the UI

if __name__ == "__main__":
    fetch_and_ingest()
