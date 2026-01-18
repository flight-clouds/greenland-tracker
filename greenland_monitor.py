"""
Greenland Airspace Monitor
Tracks all aircraft activity at Greenland airports to identify corporate/exploration traffic.

Strategy: Monitor all 14 airports + heliports. Flag any non-scheduled traffic.
Cross-reference with mineral claim database at greenmin.gl / govmin.gl

Key mining areas:
- South Greenland: Tanbreez (REE), Kvanefjeld (REE), Nalunaq (Gold), Amitsoq (Graphite)
- Kangerlussuaq: Drill core storage, White Mountain anorthosite
- West Greenland: Amaroq's Hub projects (Ge, Ga, Au)

Active companies (as of Jan 2025):
- Critical Metals Corp (CRML) - Tanbreez REE
- Amaroq Minerals (AMRQ) - Nalunaq gold, West Greenland
- Energy Transition Minerals - Kvanefjeld (uranium ban blocked)
- GreenRoc Mining - Amitsoq graphite (30-year license Dec 2025)
"""

import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from datetime import datetime, timedelta
import os
import json
import math

# ============================================================================
# GREENLAND AIRPORTS DATABASE
# Source: Naviair AIP, Wikipedia
# ============================================================================

GREENLAND_AIRPORTS = {
    # Major airports (can handle jets)
    'BGGH': {'name': 'Nuuk', 'iata': 'GOH', 'lat': 64.1909, 'lon': -51.6781, 
             'runway_m': 2200, 'type': 'major', 'notes': 'New hub since Nov 2024'},
    'BGSF': {'name': 'Kangerlussuaq', 'iata': 'SFJ', 'lat': 67.0122, 'lon': -50.7116,
             'runway_m': 2810, 'type': 'major', 'notes': 'Former hub, drill core storage nearby'},
    'BGBW': {'name': 'Narsarsuaq', 'iata': 'UAK', 'lat': 61.1605, 'lon': -45.4260,
             'runway_m': 1830, 'type': 'major', 'notes': 'South Greenland gateway - near Kvanefjeld/Tanbreez'},
    'BGTL': {'name': 'Thule/Pituffik', 'iata': 'THU', 'lat': 76.5312, 'lon': -68.7032,
             'runway_m': 3048, 'type': 'military', 'notes': 'US Space Force base'},
    'BGJN': {'name': 'Ilulissat', 'iata': 'JAV', 'lat': 69.2432, 'lon': -51.0571,
             'runway_m': 845, 'type': 'regional', 'notes': 'Expanding to 2200m in 2026'},
    'BGKK': {'name': 'Kulusuk', 'iata': 'KUS', 'lat': 65.5736, 'lon': -37.1236,
             'runway_m': 1199, 'type': 'regional', 'notes': 'East coast access'},
    
    # Regional airports
    'BGAA': {'name': 'Aasiaat', 'iata': 'JEG', 'lat': 68.7218, 'lon': -52.7847,
             'runway_m': 800, 'type': 'regional', 'notes': 'Disko Bay'},
    'BGCO': {'name': 'Nerlerit Inaat', 'iata': 'CNP', 'lat': 70.7431, 'lon': -22.6506,
             'runway_m': 1500, 'type': 'regional', 'notes': 'Northeast Greenland'},
    'BGMQ': {'name': 'Maniitsoq', 'iata': 'JSU', 'lat': 65.4125, 'lon': -52.9394,
             'runway_m': 799, 'type': 'regional', 'notes': ''},
    'BGPT': {'name': 'Paamiut', 'iata': 'JFR', 'lat': 61.9922, 'lon': -49.6625,
             'runway_m': 800, 'type': 'regional', 'notes': ''},
    'BGQQ': {'name': 'Qaanaaq', 'iata': 'NAQ', 'lat': 77.4886, 'lon': -69.3887,
             'runway_m': 900, 'type': 'regional', 'notes': 'Northernmost'},
    'BGUQ': {'name': 'Qaarsut', 'iata': 'JQA', 'lat': 70.7342, 'lon': -52.6962,
             'runway_m': 800, 'type': 'regional', 'notes': 'Uummannaq area'},
    'BGSS': {'name': 'Sisimiut', 'iata': 'JHS', 'lat': 66.9513, 'lon': -53.7293,
             'runway_m': 800, 'type': 'regional', 'notes': 'Second largest town'},
    'BGUK': {'name': 'Upernavik', 'iata': 'JUV', 'lat': 72.7902, 'lon': -56.1306,
             'runway_m': 800, 'type': 'regional', 'notes': ''},
}

# Key heliports near mining areas
MINING_HELIPORTS = {
    'BGJH': {'name': 'Qaqortoq Heliport', 'lat': 60.7158, 'lon': -46.0478,
             'notes': 'Near Tanbreez, new airport coming 2026'},
    'BGNS': {'name': 'Narsaq Heliport', 'lat': 60.9167, 'lon': -46.0500,
             'notes': 'Near Kvanefjeld REE deposit'},
    'BGNN': {'name': 'Nanortalik Heliport', 'lat': 60.1419, 'lon': -45.2328,
             'notes': 'Near Nalunaq gold mine'},
    'BGNL': {'name': 'Nalunaq Heliport', 'lat': 60.2333, 'lon': -44.8000,
             'notes': 'Amaroq gold mine site'},
}

# Known mining project locations (approximate)
MINING_PROJECTS = {
    'tanbreez': {'name': 'Tanbreez/Kringlerne', 'lat': 60.95, 'lon': -45.95,
                 'company': 'Critical Metals Corp', 'commodity': 'REE, Zr, Nb',
                 'status': 'Feasibility study'},
    'kvanefjeld': {'name': 'Kvanefjeld', 'lat': 60.98, 'lon': -45.90,
                   'company': 'Energy Transition Minerals', 'commodity': 'REE, U',
                   'status': 'Blocked - uranium ban'},
    'nalunaq': {'name': 'Nalunaq Gold Mine', 'lat': 60.23, 'lon': -44.80,
                'company': 'Amaroq Minerals', 'commodity': 'Au',
                'status': 'Producing since late 2024'},
    'amitsoq': {'name': 'Amitsoq Graphite', 'lat': 60.75, 'lon': -45.40,
                'company': 'GreenRoc Mining', 'commodity': 'Graphite',
                'status': '30-year license granted Dec 2025'},
    'white_mountain': {'name': 'White Mountain', 'lat': 66.95, 'lon': -50.90,
                       'company': 'Lumina Sustainable Materials', 'commodity': 'Anorthosite',
                       'status': 'Small-scale production'},
    'west_greenland_hub': {'name': 'West Greenland Hub', 'lat': 64.20, 'lon': -51.50,
                           'company': 'Amaroq Minerals', 'commodity': 'Ge, Ga, Cu',
                           'status': 'Exploration'},
}

# Scheduled airlines (to filter out)
SCHEDULED_OPERATORS = {
    'AirGreenland': ['GRL', 'GL'],
    'Icelandair': ['ICE', 'FI'],
    'Atlantic_Airways': ['FLI', 'RC'],
}

# Output files
CSV_FILE = 'data/greenland_traffic.csv'
MAP_FILE = 'docs/greenland_monitor.html'
ALERTS_FILE = 'data/alerts.json'

# OpenSky API
OPENSKY_URL = "https://opensky-network.org/api/states/all"


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calculate great-circle distance in kilometers using Haversine formula.
    Accurate at all latitudes including polar regions.
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def get_greenland_bbox():
    """Return bounding box for Greenland airspace."""
    # Greenland roughly spans 59°N to 84°N, 73°W to 11°W
    return {
        'lamin': 59.0,
        'lamax': 84.0,
        'lomin': -73.0,
        'lomax': -11.0
    }


def fetch_greenland_traffic(username=None, password=None):
    """
    Fetch all aircraft currently over Greenland.
    OpenSky allows bbox queries for geographic filtering.
    """
    bbox = get_greenland_bbox()
    params = {
        'lamin': bbox['lamin'],
        'lamax': bbox['lamax'],
        'lomin': bbox['lomin'],
        'lomax': bbox['lomax']
    }
    
    try:
        auth = (username, password) if username and password else None
        response = requests.get(OPENSKY_URL, params=params, auth=auth, timeout=20)
        
        if response.status_code == 429:
            print("Rate limited by OpenSky")
            return None
        elif response.status_code != 200:
            print(f"HTTP {response.status_code}")
            return None
            
        data = response.json()
        return data.get('states', [])
        
    except Exception as e:
        print(f"Error: {e}")
        return None


def classify_aircraft(callsign, icao24):
    """
    Classify aircraft as scheduled, charter, military, or unknown.
    Returns tuple: (classification, notes)
    
    ICAO24 hex ranges:
    - A00000-AFFFFF: United States (N-numbers)
    - C00000-C3FFFF: Canada (C-numbers)
    - 4xxxxx: Various European (depends on second digit)
    """
    callsign = (callsign or '').strip().upper()
    icao24 = (icao24 or '').lower()
    
    # Check scheduled operators
    for operator, codes in SCHEDULED_OPERATORS.items():
        for code in codes:
            if callsign.startswith(code):
                return ('scheduled', operator)
    
    # Military patterns
    if callsign.startswith(('RCH', 'RRR', 'CNV', 'DUKE', 'REACH')):
        return ('military', 'US Military')
    if callsign.startswith(('DAF', 'DNK')):
        return ('military', 'Danish Air Force')
    if callsign.startswith(('CFC', 'CFF', 'CANFORCE')):  # Canadian Forces
        return ('military', 'Canadian Armed Forces')
        
    # Private/corporate indicators by hex range
    if icao24.startswith('a'):  # US registration (N-numbers)
        return ('private_us', 'US-registered (N-number)')
    if icao24.startswith('c0') or icao24.startswith('c1') or icao24.startswith('c2') or icao24.startswith('c3'):
        # Canadian hex range C00000-C3FFFF
        return ('private_ca', 'Canadian-registered (C-number)')
    if icao24.startswith('4'):  # European
        return ('private_eu', 'European-registered')
        
    return ('unknown', '')


def find_nearest_airport(lat, lon):
    """Find the nearest Greenland airport to given coordinates."""
    min_dist_km = float('inf')
    nearest = None
    
    all_locations = {**GREENLAND_AIRPORTS, **MINING_HELIPORTS}
    
    for icao, info in all_locations.items():
        dist_km = haversine_km(lat, lon, info['lat'], info['lon'])
        if dist_km < min_dist_km:
            min_dist_km = dist_km
            nearest = (icao, info['name'], dist_km)
    
    return nearest


def find_nearest_mine(lat, lon, threshold_km=50):
    """
    Check if aircraft is near a known mining project.
    Returns project info if within threshold_km, else None.
    
    Default 50km threshold catches aircraft approaching/departing sites
    while filtering out unrelated overflights.
    """
    for project_id, info in MINING_PROJECTS.items():
        dist_km = haversine_km(lat, lon, info['lat'], info['lon'])
        if dist_km <= threshold_km:
            return (project_id, info['name'], info['company'], dist_km)
    return None


def process_traffic(states):
    """Process raw OpenSky data into structured records."""
    if not states:
        return []
    
    records = []
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    for state in states:
        if len(state) < 8:
            continue
            
        icao24 = state[0]
        callsign = (state[1] or '').strip()
        lon = state[5]
        lat = state[6]
        alt = state[7]
        on_ground = state[8] if len(state) > 8 else None
        velocity = state[9] if len(state) > 9 else None
        
        if lat is None or lon is None:
            continue
        
        # Classify
        classification, operator = classify_aircraft(callsign, icao24)
        
        # Find nearest locations
        nearest_apt = find_nearest_airport(lat, lon)
        nearest_mine = find_nearest_mine(lat, lon)
        
        record = {
            'timestamp': timestamp,
            'icao24': icao24,
            'callsign': callsign,
            'lat': lat,
            'lon': lon,
            'altitude_m': alt,
            'velocity_ms': velocity,
            'on_ground': on_ground,
            'classification': classification,
            'operator': operator,
            'nearest_airport': nearest_apt[1] if nearest_apt else None,
            'nearest_airport_icao': nearest_apt[0] if nearest_apt else None,
            'nearest_airport_km': round(nearest_apt[2], 1) if nearest_apt else None,
            'near_mine': nearest_mine[1] if nearest_mine else None,
            'near_mine_company': nearest_mine[2] if nearest_mine else None,
            'near_mine_km': round(nearest_mine[3], 1) if nearest_mine else None,
        }
        
        records.append(record)
        
        # Alert on interesting traffic
        if classification in ('private_us', 'private_ca', 'private_eu', 'unknown'):
            alert = f"[{timestamp}] INTERESTING: {callsign or icao24} ({classification})"
            if nearest_mine:
                alert += f" - NEAR MINING PROJECT: {nearest_mine[1]} ({nearest_mine[2]}) - {nearest_mine[3]:.0f}km"
            elif nearest_apt:
                alert += f" - near {nearest_apt[1]} ({nearest_apt[2]:.0f}km)"
            print(alert)
    
    return records


def save_data(records):
    """Append records to CSV."""
    if not records:
        return
        
    os.makedirs('data', exist_ok=True)
    df = pd.DataFrame(records)
    header = not os.path.exists(CSV_FILE)
    df.to_csv(CSV_FILE, mode='a', header=header, index=False)
    print(f"Saved {len(records)} records")


def generate_map():
    """Generate interactive map showing airports, mines, and traffic."""
    os.makedirs('docs', exist_ok=True)
    
    # Center on Greenland
    m = folium.Map(location=[72, -42], zoom_start=4, tiles='CartoDB positron')
    
    # Add airport markers
    for icao, info in GREENLAND_AIRPORTS.items():
        color = 'blue' if info['type'] == 'major' else 'lightblue'
        if info['type'] == 'military':
            color = 'red'
            
        folium.CircleMarker(
            location=[info['lat'], info['lon']],
            radius=8 if info['type'] == 'major' else 5,
            color=color,
            fill=True,
            popup=f"<b>{info['name']}</b> ({icao})<br>Runway: {info['runway_m']}m<br>{info.get('notes', '')}"
        ).add_to(m)
    
    # Add heliport markers
    for icao, info in MINING_HELIPORTS.items():
        folium.CircleMarker(
            location=[info['lat'], info['lon']],
            radius=4,
            color='green',
            fill=True,
            popup=f"<b>{info['name']}</b><br>{info.get('notes', '')}"
        ).add_to(m)
    
    # Add mining project markers
    for proj_id, info in MINING_PROJECTS.items():
        folium.Marker(
            location=[info['lat'], info['lon']],
            icon=folium.Icon(color='orange', icon='industry', prefix='fa'),
            popup=f"""<b>{info['name']}</b><br>
                     Company: {info['company']}<br>
                     Commodity: {info['commodity']}<br>
                     Status: {info['status']}"""
        ).add_to(m)
    
    # Add traffic data if available
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        # Show only interesting traffic from last 7 days
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        recent = df[df['timestamp'] > datetime.utcnow() - timedelta(days=7)]
        interesting = recent[recent['classification'].isin(['private_us', 'private_ca', 'private_eu', 'unknown'])]
        
        for _, row in interesting.iterrows():
            # Color by origin: purple=near mine, red=Canadian, blue=US, gray=other
            if row.get('near_mine'):
                color = 'purple'
            elif row['classification'] == 'private_ca':
                color = 'red'
            elif row['classification'] == 'private_us':
                color = 'blue'
            else:
                color = 'gray'
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=3,
                color=color,
                popup=f"{row['callsign'] or row['icao24']}<br>{row['classification']}<br>{row['timestamp']}<br>Near: {row.get('near_mine', row.get('nearest_airport', 'unknown'))}"
            ).add_to(m)
    
    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; background: white; 
                padding: 10px; border-radius: 5px; border: 2px solid gray; z-index: 9999;">
        <b>Legend</b><br>
        <b>Airports:</b><br>
        <span style="color: blue;">●</span> Major Airport<br>
        <span style="color: lightblue;">●</span> Regional Airport<br>
        <span style="color: red;">●</span> Military<br>
        <span style="color: green;">●</span> Mining Heliport<br>
        <span style="color: orange;">▲</span> Mining Project<br>
        <b>Aircraft:</b><br>
        <span style="color: purple;">●</span> Near Mine (any origin)<br>
        <span style="color: red;">●</span> Canadian (C-number)<br>
        <span style="color: blue;">●</span> US (N-number)<br>
        <span style="color: gray;">●</span> European/Other<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Add timestamp
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;right:10px;background:white;'
        f'padding:10px;border-radius:5px;border:1px solid gray;">'
        f'Updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</div>'
    ))
    
    m.save(MAP_FILE)
    print(f"Map saved: {MAP_FILE}")


def main():
    """Single poll - for use with cron/GitHub Actions."""
    print(f"\n=== Greenland Airspace Monitor - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} ===")
    
    states = fetch_greenland_traffic()
    
    if states:
        print(f"Found {len(states)} aircraft over Greenland")
        records = process_traffic(states)
        save_data(records)
    else:
        print("No aircraft detected or API error")
    
    generate_map()
    print("Done\n")


if __name__ == "__main__":
    main()
