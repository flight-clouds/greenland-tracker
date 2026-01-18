"""
Greenland Traffic Analyzer
Analyzes collected data to identify patterns and interesting traffic.

Run after collecting at least a few days of data.
"""

import pandas as pd
from datetime import datetime, timedelta
import os

CSV_FILE = 'data/greenland_traffic.csv'


def load_data():
    """Load and prepare traffic data."""
    if not os.path.exists(CSV_FILE):
        print("No data file found. Run greenland_monitor.py first.")
        return None
    
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def find_repeat_visitors(df, min_visits=2, days=30):
    """
    Find aircraft that have visited Greenland multiple times.
    These are most likely to be exploration-related.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = df[df['timestamp'] > cutoff]
    
    # Count visits by aircraft
    visits = recent.groupby('icao24').agg({
        'timestamp': 'count',
        'callsign': lambda x: ', '.join(x.dropna().unique()),
        'nearest_airport': lambda x: ', '.join(x.dropna().unique()),
        'near_mine': lambda x: ', '.join(x.dropna().unique()),
        'classification': 'first'
    }).rename(columns={'timestamp': 'visit_count'})
    
    repeat = visits[visits['visit_count'] >= min_visits].sort_values('visit_count', ascending=False)
    return repeat


def find_mine_proximate_traffic(df):
    """Find all traffic that passed near known mining projects."""
    mine_traffic = df[df['near_mine'].notna()]
    
    summary = mine_traffic.groupby(['near_mine', 'near_mine_company']).agg({
        'icao24': lambda x: list(x.unique()),
        'timestamp': ['min', 'max', 'count']
    })
    
    return summary


def find_unusual_airports(df):
    """
    Find traffic at airports that don't normally see private jets.
    Small regional airports with private traffic = exploration indicator.
    """
    # Regional airports that rarely see bizjets
    unusual_airports = ['BGCO', 'BGQQ', 'BGUQ', 'BGUK', 'BGMQ', 'BGPT']
    
    private_traffic = df[df['classification'].isin(['private_us', 'private_eu', 'unknown'])]
    unusual = private_traffic[private_traffic['nearest_airport_icao'].isin(unusual_airports)]
    
    return unusual


def identify_hex_registration(icao24):
    """
    Attempt to identify aircraft registration from hex code.
    US registrations (N-numbers) can be computed from hex.
    """
    if not icao24 or not icao24.startswith('a'):
        return None
    
    # US hex codes start with 'a'
    # This is a simplified lookup - full conversion is complex
    # For real use, query: https://hexdb.io/api/v1/aircraft/{hex}
    return f"US-registered (lookup {icao24} at hexdb.io)"


def generate_report(df):
    """Generate summary report of interesting findings."""
    print("\n" + "="*60)
    print("GREENLAND AIRSPACE ANALYSIS REPORT")
    print(f"Data period: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Total observations: {len(df)}")
    print("="*60)
    
    # Traffic breakdown
    print("\n--- Traffic Classification ---")
    print(df['classification'].value_counts())
    
    # Repeat visitors
    print("\n--- Repeat Visitors (last 30 days) ---")
    repeats = find_repeat_visitors(df)
    if len(repeats) > 0:
        print(repeats.to_string())
    else:
        print("No repeat visitors detected yet")
    
    # Mine-proximate traffic
    print("\n--- Traffic Near Mining Projects ---")
    mine_traffic = find_mine_proximate_traffic(df)
    if len(mine_traffic) > 0:
        print(mine_traffic.to_string())
    else:
        print("No traffic detected near mining projects")
    
    # Unusual airport traffic
    print("\n--- Private Traffic at Unusual Airports ---")
    unusual = find_unusual_airports(df)
    if len(unusual) > 0:
        print(unusual[['timestamp', 'icao24', 'callsign', 'nearest_airport', 'classification']].to_string())
    else:
        print("No unusual airport traffic detected")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    df = load_data()
    if df is not None:
        generate_report(df)
