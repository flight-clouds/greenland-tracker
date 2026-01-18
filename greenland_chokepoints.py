"""
Greenland Mining Intelligence Tracker
=====================================
Focused monitoring of the 3 jet-capable airports that funnel ALL corporate traffic.

Strategy: Executives fly private to nearest jet strip, then helicopter to camp.
We monitor the "choke points" where they MUST land.

PRIORITY AIRPORTS:
┌─────────────────┬──────┬─────────────┬─────────────────────────────────────┐
│ Airport         │ ICAO │ Signal      │ Why                                 │
├─────────────────┼──────┼─────────────┼─────────────────────────────────────┤
│ Narsarsuaq      │ BGBW │ 🚨 RED      │ THE Mining Hub. Next to Tanbreez,   │
│                 │      │             │ Kvanefjeld. Bizjet here = mining.   │
├─────────────────┼──────┼─────────────┼─────────────────────────────────────┤
│ Nuuk            │ BGGH │ 🟡 YELLOW   │ Political Hub. Mixed traffic:       │
│                 │      │             │ diplomats, govt, mining HQ deals.   │
├─────────────────┼──────┼─────────────┼─────────────────────────────────────┤
│ Kangerlussuaq   │ BGSF │ ⚪ LOW      │ Old Hub. Mostly military, science,  │
│                 │      │             │ diverted commercial. Less signal.   │
└─────────────────┴──────┴─────────────┴─────────────────────────────────────┘

DETECTION PATTERN:
1. US/Canadian bizjet lands at BGBW
2. Stays on ground 6-8+ hours (site visit duration)
3. Helicopter departs to "nowhere" (into the mountains)
4. Cross-reference with claim activity on greenmin.gl
"""

import requests
import pandas as pd
import folium
from datetime import datetime, timedelta
import os
import json
import math

# =============================================================================
# CHOKE POINT AIRPORTS - The only places corporate jets can land
# =============================================================================

CHOKE_POINTS = {
    'BGBW': {
        'name': 'Narsarsuaq',
        'iata': 'UAK',
        'lat': 61.1605,
        'lon': -45.4260,
        'runway_m': 1830,
        'signal': 'RED',
        'signal_emoji': '🚨',
        'notes': 'THE Mining Hub - Tanbreez, Kvanefjeld, Nalunaq, Amitsoq all nearby',
        'nearby_projects': ['Tanbreez', 'Kvanefjeld', 'Nalunaq', 'Amitsoq'],
        'monitoring_radius_km': 50,  # Capture approaches/departures
    },
    'BGGH': {
        'name': 'Nuuk',
        'iata': 'GOH', 
        'lat': 64.1909,
        'lon': -51.6781,
        'runway_m': 2200,
        'signal': 'YELLOW',
        'signal_emoji': '🟡',
        'notes': 'Political Hub - diplomats, government, mining HQ meetings',
        'nearby_projects': ['West Greenland Hub'],
        'monitoring_radius_km': 40,
    },
    'BGSF': {
        'name': 'Kangerlussuaq',
        'iata': 'SFJ',
        'lat': 67.0122,
        'lon': -50.7116,
        'runway_m': 2810,
        'signal': 'LOW',
        'signal_emoji': '⚪',
        'notes': 'Old Hub - military, science, diversions. Less mining signal.',
        'nearby_projects': ['White Mountain'],
        'monitoring_radius_km': 40,
    },
}

# Mining projects for context
MINING_PROJECTS = {
    'tanbreez': {
        'name': 'Tanbreez/Kringlerne',
        'lat': 60.95, 'lon': -45.95,
        'company': 'Critical Metals Corp (CRML)',
        'commodity': 'REE, Zr, Nb',
        'nearest_airport': 'BGBW',
    },
    'kvanefjeld': {
        'name': 'Kvanefjeld',
        'lat': 60.98, 'lon': -45.90,
        'company': 'Energy Transition Minerals',
        'commodity': 'REE (blocked - uranium)',
        'nearest_airport': 'BGBW',
    },
    'nalunaq': {
        'name': 'Nalunaq Gold Mine',
        'lat': 60.23, 'lon': -44.80,
        'company': 'Amaroq Minerals (AMRQ)',
        'commodity': 'Au',
        'nearest_airport': 'BGBW',
    },
    'amitsoq': {
        'name': 'Amitsoq Graphite',
        'lat': 60.75, 'lon': -45.40,
        'company': 'GreenRoc Mining',
        'commodity': 'Graphite',
        'nearest_airport': 'BGBW',
    },
    'west_hub': {
        'name': 'West Greenland Hub',
        'lat': 64.20, 'lon': -51.50,
        'company': 'Amaroq Minerals',
        'commodity': 'Ge, Ga, Cu',
        'nearest_airport': 'BGGH',
    },
}

# Scheduled traffic to filter out
SCHEDULED_CALLSIGN_PREFIXES = [
    'GRL',   # Air Greenland
    'ICE',   # Icelandair
    'FLI',   # Atlantic Airways
    'SAS',   # SAS
    'DAT',   # Danish Air Transport
]

# Files
DATA_DIR = 'data'
ARRIVALS_FILE = f'{DATA_DIR}/choke_point_arrivals.csv'
ALERTS_FILE = f'{DATA_DIR}/priority_alerts.json'
DWELL_FILE = f'{DATA_DIR}/aircraft_dwell.json'
MAP_FILE = 'docs/greenland_chokepoints.html'

# OpenSky
OPENSKY_URL = "https://opensky-network.org/api/states/all"


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometers using Haversine formula."""
    R = 6371
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def classify_aircraft(callsign, icao24):
    """
    Classify aircraft by registration origin and type.
    
    Returns: (priority, classification, notes)
    - priority: 1 (highest) to 5 (lowest)
    """
    callsign = (callsign or '').strip().upper()
    icao24 = (icao24 or '').lower()
    
    # Filter scheduled traffic
    for prefix in SCHEDULED_CALLSIGN_PREFIXES:
        if callsign.startswith(prefix):
            return (5, 'scheduled', f'Scheduled: {prefix}')
    
    # Military
    if callsign.startswith(('RCH', 'RRR', 'REACH', 'CNV', 'DUKE')):
        return (4, 'military_us', 'US Military')
    if callsign.startswith(('DAF', 'DNK', 'DANSUP')):
        return (4, 'military_dk', 'Danish Military')
    if callsign.startswith(('CFC', 'CFF', 'CANFORCE')):
        return (4, 'military_ca', 'Canadian Military')
    
    # HIGH PRIORITY: US/Canadian corporate jets
    if icao24.startswith('a'):
        return (1, 'private_us', 'US N-number - PRIORITY TARGET')
    if icao24.startswith(('c0', 'c1', 'c2', 'c3')):
        return (1, 'private_ca', 'Canadian C-number - PRIORITY TARGET')
    
    # Medium priority: European corporate
    if icao24.startswith('4'):
        return (2, 'private_eu', 'European registration')
    
    # Icelandic (common for charters to Greenland)
    if icao24.startswith('tf'):
        return (2, 'private_is', 'Icelandic registration')
    
    return (3, 'unknown', 'Unknown registration')


def fetch_airport_traffic(airport_icao, radius_km, username=None, password=None):
    """
    Fetch aircraft within radius of a specific airport.
    Uses bbox query centered on airport.
    """
    airport = CHOKE_POINTS.get(airport_icao)
    if not airport:
        return []
    
    # Convert radius to rough lat/lon box (overestimate to ensure coverage)
    # At 65°N, 1° lon ≈ 47km, 1° lat ≈ 111km
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(airport['lat'])))
    
    params = {
        'lamin': airport['lat'] - lat_delta,
        'lamax': airport['lat'] + lat_delta,
        'lomin': airport['lon'] - lon_delta,
        'lomax': airport['lon'] + lon_delta,
    }
    
    try:
        auth = (username, password) if username and password else None
        response = requests.get(OPENSKY_URL, params=params, auth=auth, timeout=15)
        
        if response.status_code == 429:
            print(f"  Rate limited")
            return None
        if response.status_code != 200:
            print(f"  HTTP {response.status_code}")
            return None
            
        data = response.json()
        states = data.get('states', [])
        
        # Filter to actual radius (bbox is square, we want circle)
        filtered = []
        for state in states:
            if len(state) < 8 or state[5] is None or state[6] is None:
                continue
            dist = haversine_km(airport['lat'], airport['lon'], state[6], state[5])
            if dist <= radius_km:
                filtered.append(state)
        
        return filtered
        
    except Exception as e:
        print(f"  Error: {e}")
        return None


def process_aircraft(state, airport_icao):
    """Process a single aircraft state into a record."""
    icao24 = state[0]
    callsign = (state[1] or '').strip()
    lon, lat = state[5], state[6]
    altitude = state[7]  # meters
    on_ground = state[8] if len(state) > 8 else None
    velocity = state[9] if len(state) > 9 else None
    
    airport = CHOKE_POINTS[airport_icao]
    distance_km = haversine_km(airport['lat'], airport['lon'], lat, lon)
    
    priority, classification, notes = classify_aircraft(callsign, icao24)
    
    # Determine if aircraft is likely landing/departing vs overflying
    is_low = altitude is not None and altitude < 3000  # Below 10,000 ft
    is_slow = velocity is not None and velocity < 100  # Below ~195 knots
    likely_arrival = (on_ground or (is_low and is_slow)) and distance_km < 20
    
    return {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'airport_icao': airport_icao,
        'airport_name': airport['name'],
        'airport_signal': airport['signal'],
        'icao24': icao24,
        'callsign': callsign,
        'lat': lat,
        'lon': lon,
        'altitude_m': altitude,
        'velocity_ms': velocity,
        'on_ground': on_ground,
        'distance_km': round(distance_km, 1),
        'likely_arrival': likely_arrival,
        'priority': priority,
        'classification': classification,
        'classification_notes': notes,
    }


def update_dwell_tracking(records):
    """
    Track how long aircraft stay at airports.
    Key signal: bizjet on ground for 6-8+ hours = site visit.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Load existing dwell data
    if os.path.exists(DWELL_FILE):
        with open(DWELL_FILE, 'r') as f:
            dwell_data = json.load(f)
    else:
        dwell_data = {}
    
    current_time = datetime.utcnow()
    
    for record in records:
        if not record['on_ground']:
            continue
        if record['priority'] > 2:  # Only track priority targets
            continue
            
        key = f"{record['icao24']}_{record['airport_icao']}"
        
        if key not in dwell_data:
            dwell_data[key] = {
                'icao24': record['icao24'],
                'callsign': record['callsign'],
                'airport': record['airport_name'],
                'airport_icao': record['airport_icao'],
                'first_seen': record['timestamp'],
                'last_seen': record['timestamp'],
                'classification': record['classification'],
            }
        else:
            dwell_data[key]['last_seen'] = record['timestamp']
            if record['callsign']:
                dwell_data[key]['callsign'] = record['callsign']
    
    # Calculate dwell times and flag long stays
    alerts = []
    for key, data in dwell_data.items():
        first = datetime.strptime(data['first_seen'], '%Y-%m-%d %H:%M:%S')
        last = datetime.strptime(data['last_seen'], '%Y-%m-%d %H:%M:%S')
        dwell_hours = (last - first).total_seconds() / 3600
        data['dwell_hours'] = round(dwell_hours, 1)
        
        # Alert on extended stays (site visit pattern)
        if dwell_hours >= 4 and data['airport_icao'] == 'BGBW':
            alerts.append({
                'type': 'EXTENDED_DWELL',
                'priority': 'HIGH',
                'message': f"🚨 {data['callsign'] or data['icao24']} on ground at Narsarsuaq for {dwell_hours:.1f} hours",
                'data': data,
            })
    
    # Clean old entries (>48 hours since last seen)
    cutoff = current_time - timedelta(hours=48)
    dwell_data = {k: v for k, v in dwell_data.items() 
                  if datetime.strptime(v['last_seen'], '%Y-%m-%d %H:%M:%S') > cutoff}
    
    with open(DWELL_FILE, 'w') as f:
        json.dump(dwell_data, f, indent=2)
    
    return alerts


def save_records(records):
    """Save arrival records to CSV."""
    if not records:
        return
        
    os.makedirs(DATA_DIR, exist_ok=True)
    df = pd.DataFrame(records)
    header = not os.path.exists(ARRIVALS_FILE)
    df.to_csv(ARRIVALS_FILE, mode='a', header=header, index=False)


def generate_priority_alert(record):
    """Generate alert for priority traffic."""
    airport = CHOKE_POINTS[record['airport_icao']]
    
    if record['priority'] == 1 and airport['signal'] == 'RED':
        return {
            'timestamp': record['timestamp'],
            'level': 'CRITICAL',
            'emoji': '🚨🚨🚨',
            'message': f"US/CA BIZJET AT NARSARSUAQ: {record['callsign'] or record['icao24']}",
            'details': f"{record['classification_notes']} | {record['distance_km']}km from airport | Alt: {record['altitude_m']}m",
            'action': 'Cross-reference with greenmin.gl claim activity. Check hex at hexdb.io.',
            'record': record,
        }
    elif record['priority'] == 1:
        return {
            'timestamp': record['timestamp'],
            'level': 'HIGH',
            'emoji': '🟡',
            'message': f"US/CA aircraft at {airport['name']}: {record['callsign'] or record['icao24']}",
            'details': record['classification_notes'],
            'record': record,
        }
    elif record['priority'] == 2 and airport['signal'] == 'RED':
        return {
            'timestamp': record['timestamp'],
            'level': 'MEDIUM',
            'emoji': '📍',
            'message': f"European aircraft at Narsarsuaq: {record['callsign'] or record['icao24']}",
            'details': record['classification_notes'],
            'record': record,
        }
    return None


def generate_map():
    """Generate focused map showing choke points and recent priority traffic."""
    os.makedirs('docs', exist_ok=True)
    
    # Center on South Greenland (where the action is)
    m = folium.Map(location=[63, -48], zoom_start=5, tiles='CartoDB positron')
    
    # Add choke point airports with signal-colored markers
    for icao, info in CHOKE_POINTS.items():
        if info['signal'] == 'RED':
            color = 'red'
            icon = 'plane'
        elif info['signal'] == 'YELLOW':
            color = 'orange'
            icon = 'plane'
        else:
            color = 'gray'
            icon = 'plane'
        
        # Add monitoring radius circle
        folium.Circle(
            location=[info['lat'], info['lon']],
            radius=info['monitoring_radius_km'] * 1000,
            color=color,
            fill=True,
            fillOpacity=0.1,
            popup=f"Monitoring radius: {info['monitoring_radius_km']}km"
        ).add_to(m)
        
        # Add airport marker
        folium.Marker(
            location=[info['lat'], info['lon']],
            icon=folium.Icon(color=color, icon=icon, prefix='fa'),
            popup=f"""<b>{info['signal_emoji']} {info['name']}</b> ({icao})<br>
                     Signal: {info['signal']}<br>
                     Runway: {info['runway_m']}m<br>
                     {info['notes']}<br>
                     <br>
                     <b>Nearby projects:</b> {', '.join(info['nearby_projects'])}"""
        ).add_to(m)
    
    # Add mining projects
    for proj_id, info in MINING_PROJECTS.items():
        folium.CircleMarker(
            location=[info['lat'], info['lon']],
            radius=6,
            color='purple',
            fill=True,
            popup=f"""<b>{info['name']}</b><br>
                     {info['company']}<br>
                     {info['commodity']}<br>
                     Nearest airport: {info['nearest_airport']}"""
        ).add_to(m)
    
    # Add recent priority traffic
    if os.path.exists(ARRIVALS_FILE):
        df = pd.read_csv(ARRIVALS_FILE)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        recent = df[df['timestamp'] > datetime.utcnow() - timedelta(days=7)]
        priority = recent[recent['priority'] <= 2]
        
        for _, row in priority.iterrows():
            color = 'darkred' if row['priority'] == 1 else 'blue'
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=4,
                color=color,
                fill=True,
                popup=f"""<b>{row['callsign'] or row['icao24']}</b><br>
                         {row['classification']}<br>
                         {row['timestamp']}<br>
                         {row['airport_name']} ({row['distance_km']}km)<br>
                         {'ON GROUND' if row['on_ground'] else f"Alt: {row['altitude_m']}m"}"""
            ).add_to(m)
    
    # Add dwell alerts
    if os.path.exists(DWELL_FILE):
        with open(DWELL_FILE, 'r') as f:
            dwell_data = json.load(f)
        
        for key, data in dwell_data.items():
            if data.get('dwell_hours', 0) >= 4:
                airport = CHOKE_POINTS.get(data['airport_icao'], {})
                if airport:
                    folium.Marker(
                        location=[airport['lat'], airport['lon']],
                        icon=folium.Icon(color='darkred', icon='clock', prefix='fa'),
                        popup=f"""<b>⏱️ EXTENDED STAY</b><br>
                                 {data['callsign'] or data['icao24']}<br>
                                 {data['dwell_hours']} hours on ground<br>
                                 {data['classification']}"""
                    ).add_to(m)
    
    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; background: white; 
                padding: 15px; border-radius: 5px; border: 2px solid gray; z-index: 9999; font-size: 12px;">
        <b>Greenland Choke Points</b><br><br>
        <b>Airports:</b><br>
        🚨 <span style="color: red;">●</span> RED - Narsarsuaq (Mining Hub)<br>
        🟡 <span style="color: orange;">●</span> YELLOW - Nuuk (Political)<br>
        ⚪ <span style="color: gray;">●</span> LOW - Kangerlussuaq (Noise)<br><br>
        <b>Traffic:</b><br>
        <span style="color: darkred;">●</span> US/Canadian (Priority 1)<br>
        <span style="color: blue;">●</span> European (Priority 2)<br>
        <span style="color: purple;">●</span> Mining Project<br>
        ⏱️ Extended ground stay (4+ hrs)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Timestamp
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;right:10px;background:white;'
        f'padding:10px;border-radius:5px;border:1px solid gray;font-size:11px;">'
        f'<b>Greenland Mining Intel</b><br>'
        f'Updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</div>'
    ))
    
    m.save(MAP_FILE)
    print(f"Map saved: {MAP_FILE}")


def main():
    """
    Main monitoring loop - polls each choke point.
    Run via cron/GitHub Actions every 15-30 minutes.
    """
    print(f"\n{'='*60}")
    print(f"GREENLAND CHOKE POINT MONITOR")
    print(f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*60}")
    
    username = os.environ.get('OPENSKY_USER')
    password = os.environ.get('OPENSKY_PASS')
    
    all_records = []
    all_alerts = []
    
    # Poll each choke point (prioritize Narsarsuaq)
    for icao in ['BGBW', 'BGGH', 'BGSF']:
        airport = CHOKE_POINTS[icao]
        print(f"\n{airport['signal_emoji']} Checking {airport['name']} ({icao})...")
        
        states = fetch_airport_traffic(icao, airport['monitoring_radius_km'], username, password)
        
        if states is None:
            print(f"  API error, skipping")
            continue
        
        if not states:
            print(f"  No aircraft detected")
            continue
            
        print(f"  Found {len(states)} aircraft")
        
        for state in states:
            record = process_aircraft(state, icao)
            all_records.append(record)
            
            # Generate alerts for priority traffic
            alert = generate_priority_alert(record)
            if alert:
                all_alerts.append(alert)
                print(f"  {alert['emoji']} {alert['message']}")
    
    # Save data
    save_records(all_records)
    print(f"\nSaved {len(all_records)} records")
    
    # Update dwell tracking
    dwell_alerts = update_dwell_tracking(all_records)
    all_alerts.extend(dwell_alerts)
    
    # Save alerts
    if all_alerts:
        os.makedirs(DATA_DIR, exist_ok=True)
        # Append to alerts file
        existing_alerts = []
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, 'r') as f:
                existing_alerts = json.load(f)
        
        # Add new alerts (keep last 100)
        for alert in all_alerts:
            # Remove non-serializable record data
            alert_clean = {k: v for k, v in alert.items() if k != 'record'}
            existing_alerts.append(alert_clean)
        
        existing_alerts = existing_alerts[-100:]
        
        with open(ALERTS_FILE, 'w') as f:
            json.dump(existing_alerts, f, indent=2)
        
        print(f"\n🚨 {len(all_alerts)} PRIORITY ALERTS:")
        for alert in all_alerts:
            print(f"  {alert['emoji']} [{alert['level']}] {alert['message']}")
    
    # Generate map
    generate_map()
    
    print(f"\n{'='*60}")
    print("Done")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
