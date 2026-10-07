#!/usr/bin/env python3
"""Generate incidents-trackflow.csv per CONTEXT_2.md spec."""
import csv
import sys

carriers_us = ["UPS", "FEDEX", "DHL_US"]
carriers_es = ["MRW", "SEUR", "DHL_ES", "LOCAL_ES"]
categories = ["LOST_PARCEL", "DELAYED_DELIVERY", "WRONG_ADDRESS", "RETURN_REQUEST", "DAMAGE"]
statuses = ["OPEN", "CLOSED", "DISCARDED"]

# Distribution targets (valid = 95)
cat_targets = {"LOST_PARCEL": 14, "DELAYED_DELIVERY": 38, "WRONG_ADDRESS": 19, "RETURN_REQUEST": 17, "DAMAGE": 7}
status_targets = {"OPEN": 29, "CLOSED": 52, "DISCARDED": 14}
country_targets = {"US": 50, "ES": 45}
sat_scores_closed = [1]*6 + [2]*11 + [3]*15 + [4]*14 + [5]*6  # 52 scores

rows = []
id_counter = 1

def next_id():
    global id_counter
    i = id_counter
    id_counter += 1
    return f"TRF-{i:06d}"

# Generate 95 valid records
for cat, target in cat_targets.items():
    for _ in range(target):
        rid = next_id()
        if cat_targets[cat] <= 0:
            continue
        # Pick country to match country_targets
        if country_targets["US"] > 0:
            country = "US"
            country_targets["US"] -= 1
        elif country_targets["ES"] > 0:
            country = "ES"
            country_targets["ES"] -= 1
        else:
            country = "ES"  # fallback

        carrier = carriers_us[0] if country == "US" else carriers_es[0]

        # Pick status
        for st, st_target in list(status_targets.items()):
            if st_target > 0:
                status = st
                status_targets[st] -= 1
                break
        else:
            status = "OPEN"

        satisfaction = ""
        if status == "CLOSED":
            if sat_scores_closed:
                satisfaction = str(sat_scores_closed.pop(0))
            else:
                satisfaction = "3"

        rows.append({
            "incident_id": rid,
            "date": "2026-09-15",
            "country": country,
            "customer_type": "B2B" if rid <= "TRF-000050" else "B2C",
            "tracking_number": f"TRACK{rid[-6:]}",
            "carrier": carrier,
            "category": cat,
            "description": f"Incident regarding {cat.lower().replace('_', ' ')}",
            "status": status,
            "customer_email": f"customer{rid[-4:]}@example.com",
            "satisfaction_score": satisfaction,
        })

# Add 5 invalid records
invalid_cases = [
    # 1. Missing tracking_number (too short)
    {"incident_id": next_id(), "date": "2026-09-15", "country": "US", "customer_type": "B2C",
     "tracking_number": "SHORT", "carrier": "UPS", "category": "LOST_PARCEL",
     "description": "Missing tracking number", "status": "OPEN",
     "customer_email": "bad-tracking@example.com", "satisfaction_score": ""},
    # 2. Carrier/country mismatch (US carrier in ES)
    {"incident_id": next_id(), "date": "2026-09-15", "country": "ES", "customer_type": "B2C",
     "tracking_number": "TRACK000099", "carrier": "UPS", "category": "DAMAGE",
     "description": "Carrier mismatch test", "status": "OPEN",
     "customer_email": "carrier-mismatch@example.com", "satisfaction_score": ""},
    # 3. Invalid category
    {"incident_id": next_id(), "date": "2026-09-15", "country": "US", "customer_type": "B2C",
     "tracking_number": "TRACK000100", "carrier": "UPS", "category": "INVALID_CAT",
     "description": "Bad category test", "status": "OPEN",
     "customer_email": "bad-category@example.com", "satisfaction_score": ""},
    # 4. Invalid email
    {"incident_id": next_id(), "date": "2026-09-15", "country": "US", "customer_type": "B2C",
     "tracking_number": "TRACK000101", "carrier": "FEDEX", "category": "WRONG_ADDRESS",
     "description": "Bad email test", "status": "CLOSED",
     "customer_email": "not-an-email", "satisfaction_score": "3"},
    # 5. Closed but no satisfaction_score
    {"incident_id": next_id(), "date": "2026-09-15", "country": "ES", "customer_type": "B2B",
     "tracking_number": "TRACK000102", "carrier": "SEUR", "category": "DELAYED_DELIVERY",
     "description": "Closed missing score test", "status": "CLOSED",
     "customer_email": "no-score@example.com", "satisfaction_score": ""},
]

rows.extend(invalid_cases)

# Write CSV
headers = ["incident_id","date","country","customer_type","tracking_number","carrier","category","description","status","customer_email","satisfaction_score"]
try:
    with open("data/incidents-trackflow.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)
except OSError:
    print("Could not write the incident fixture CSV.", file=sys.stderr)
    sys.exit(1)

print(f"Generated {len(rows)} rows in data/incidents-trackflow.csv")
# Verify counts
valid = [r for r in rows if r["incident_id"] not in [inv["incident_id"] for inv in invalid_cases]]
print(f"Valid: {len(valid)}, Invalid: {len(rows)-len(valid)}")
from collections import Counter
cats = Counter(r["category"] for r in valid)
print(f"Categories: {dict(cats)}")
stats = Counter(r["status"] for r in valid)
print(f"Statuses: {dict(stats)}")
countries = Counter(r["country"] for r in valid)
print(f"Countries: {dict(countries)}")
closed_scores = [int(r["satisfaction_score"]) for r in valid if r["status"] == "CLOSED" and r["satisfaction_score"]]
print(f"Closed scored: {len(closed_scores)}")
if closed_scores:
    print(f"Avg satisfaction: {sum(closed_scores)/len(closed_scores):.2f}")
    print(f"Score dist: {dict(Counter(closed_scores))}")