# Greenland Mining Intelligence Tracker 🇬🇱

Focused monitoring of corporate jet traffic at Greenland's 3 jet-capable airports.

## The Strategy

**Problem:** ADS-B coverage over Greenland is poor. Trying to track aircraft over the entire island is spray-and-pray.

**Solution:** Executives can't teleport. They MUST land at one of only 3 airports capable of handling a Gulfstream or Global Express. We monitor these "choke points" instead.

### The Executive Commute Pattern

Mining executives and investors don't fly commercial to Nuuk and take a 4-hour boat ride. They:

1. **Fly private** directly to the nearest jet-capable airport
2. **Charter a helicopter** for the "last mile" to the exploration camp
3. **Stay 6-8 hours** for the site visit
4. **Fly out** the same day or next morning

We catch them at step 1.

## The 3 Choke Points

| Airport | ICAO | Signal | Why Watch It |
|---------|------|--------|--------------|
| **Narsarsuaq** | `BGBW` | 🚨 **RED** | THE Mining Hub. Former US airbase, literally next door to Tanbreez (world's largest REE deposit), Kvanefjeld, Nalunaq gold mine, Amitsoq graphite. A bizjet here is almost certainly mining-related. |
| **Nuuk** | `BGGH` | 🟡 **YELLOW** | Political Hub. New international runway (Nov 2024) allows direct flights from NYC/London. Mixed traffic: diplomats, government meetings, mining HQ deals. Harder to filter. |
| **Kangerlussuaq** | `BGSF` | ⚪ **LOW** | Old Hub. Historically the only big runway, now mostly military, scientific logistics, diverted commercial. Less likely to be a pure mining play. |

### Priority Order

**If you see a US or Canadian bizjet at Narsarsuaq, that's the money shot.**

## Detection Signals

### 🚨 CRITICAL (Priority 1 at BGBW)
- US-registered aircraft (hex `A00000-AFFFFF`) at Narsarsuaq
- Canadian-registered aircraft (hex `C00000-C3FFFF`) at Narsarsuaq
- Extended ground time (4+ hours) at Narsarsuaq

### 🟡 HIGH (Priority 1 elsewhere, Priority 2 at BGBW)  
- US/Canadian aircraft at Nuuk or Kangerlussuaq
- European bizjets (hex `4xxxxx`) at Narsarsuaq

### ⚪ NOISE (Filter out)
- Air Greenland scheduled (callsign `GRL`)
- Icelandair (`ICE`)
- Atlantic Airways (`FLI`)
- Danish/US military (`DAF`, `RCH`)

## Mining Projects Near Narsarsuaq

| Project | Company | Commodity | Status |
|---------|---------|-----------|--------|
| **Tanbreez/Kringlerne** | Critical Metals Corp (CRML) | REE, Zr, Nb | Feasibility study - potentially world's largest REE deposit |
| **Kvanefjeld** | Energy Transition Minerals | REE | Blocked by uranium mining ban |
| **Nalunaq** | Amaroq Minerals (AMRQ) | Gold | Producing since late 2024 |
| **Amitsoq** | GreenRoc Mining | Graphite | 30-year license granted Dec 2025 |

## What the Data Tells You

### High-Confidence Signals
1. **Same aircraft, multiple visits** → Active due diligence
2. **US/CA bizjet + 6-8hr ground time** → Site visit pattern
3. **Cluster of visits from different companies** → Hot prospect, competitive interest
4. **Timing correlation with claim filings** → Deal in progress

### Cross-Reference Workflow
1. Spot priority aircraft at Narsarsuaq
2. Get hex code → lookup at [hexdb.io](https://hexdb.io)
3. Get N-number → lookup owner via FAA registry
4. Check [greenmin.gl](https://www.greenmin.gl/map/) for recent claim activity in area
5. Monitor for repeat visits over coming weeks

## Files

```
├── greenland_chokepoints.py    # Main focused tracker
├── greenland_monitor.py        # Legacy full-airspace monitor (less useful)
├── analyze.py                  # Pattern analysis
├── data/
│   ├── choke_point_arrivals.csv   # All detected traffic
│   ├── priority_alerts.json       # High-priority detections
│   └── aircraft_dwell.json        # Ground time tracking
└── docs/
    └── greenland_chokepoints.html # Live map
```

## Quick Start

```bash
unzip greenland-monitor.zip
cd greenland_tracker
pip install requests pandas folium

# Test locally
python greenland_chokepoints.py

# View map
open docs/greenland_chokepoints.html
```

See `DEPLOYMENT.md` for full GitHub Actions setup.

## API Efficiency

The choke point strategy is also more API-efficient:

| Approach | API Calls/Run | Coverage |
|----------|---------------|----------|
| Full Greenland bbox | 1 large query | Poor (sparse receivers) |
| **3 focused queries** | 3 small queries | Good (airports have receivers) |

Airports have ADS-B receivers. Remote mountains don't.

## Limitations

- **Helicopter blind spot**: The last-mile helicopter to the mine site usually isn't tracked
- **Charter aircraft**: May use Icelandic-registered aircraft (TF-xxx) which blend in
- **Tourism noise at Narsarsuaq**: Some adventure tourism uses private jets (rare but possible)
- **Winter**: Exploration season is May-September; winter traffic is mostly logistics

## License

MIT - For research purposes. 

---

*"You don't need to see them at the mine. You just need to see them at the only door."*
