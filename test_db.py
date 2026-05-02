"""Verify matches in DB."""
import requests

r = requests.get("http://127.0.0.1:8080/api/v2/matches?limit=50")
data = r.json()
print(f"Total matches: {data['total']}")
print()
for m in data["matches"]:
    num = m["match_number"] or "?"
    t1 = m["team1"] or "?"
    t2 = m["team2"] or "?"
    status = m["status"]
    print(f"  #{num:>3}: {t1} vs {t2} [{status}]")
