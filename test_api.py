"""Quick API test script for the Fantasy Points System."""
import json
import requests
import sys

BASE = "http://127.0.0.1:8080"
URL = "https://www.espncricinfo.com/series/ipl-2026-1510719/rajasthan-royals-vs-sunrisers-hyderabad-36th-match-1529279/full-scorecard"


def test_health():
    r = requests.get(f"{BASE}/health")
    print(f"[HEALTH] {r.status_code}: {r.json()}")
    assert r.status_code == 200
    return True


def test_scrape():
    print(f"\n{'='*60}")
    print("[SCRAPE] Sending request...")
    r = requests.post(f"{BASE}/api/scrape", json={"url": URL})
    print(f"[SCRAPE] Status: {r.status_code}")
    if r.status_code != 200:
        print(f"[SCRAPE] ERROR: {r.text[:2000]}")
        return None

    data = r.json()
    print(f"  match_id:   {data['match_id']}")
    print(f"  title:      {data['match_title']}")
    print(f"  teams:      {data['team1']} vs {data['team2']}")
    print(f"  result:     {data['result']}")
    print(f"  innings:    {len(data['innings'])}")
    for i, inn in enumerate(data["innings"]):
        print(f"    Innings {i+1} ({inn['team_name']}):")
        print(f"      Batters:  {len(inn['batting'])}")
        print(f"      Bowlers:  {len(inn['bowling'])}")
        print(f"      Fielders: {len(inn['fielding'])}")
        print(f"      DNB:      {len(inn['did_not_bat'])}")
        print(f"      Extras:   {inn['extras']}, Total: {inn['total_runs']}/{inn['total_wickets']} ({inn['total_overs']} ov)")
        for b in inn["batting"]:
            print(f"        {b['name']:25s} {b['runs']:3d}({b['balls']:2d})  {b['fours']}x4 {b['sixes']}x6  SR={b['strike_rate']:.2f}  [{b['dismissal']}]")
    return data["match_id"]


def test_calculate_points(match_id):
    print(f"\n{'='*60}")
    print(f"[POINTS] Calculating points for match {match_id}...")
    r = requests.post(f"{BASE}/api/calculate-points", json={"match_id": match_id})
    print(f"[POINTS] Status: {r.status_code}")
    if r.status_code != 200:
        print(f"[POINTS] ERROR: {r.text[:2000]}")
        return False

    data = r.json()
    print(f"  Players: {len(data['players'])}")
    print(f"\n  {'Name':25s} {'Team':22s} {'Bat':>5s} {'Bowl':>5s} {'Field':>5s} {'Total':>6s}")
    print(f"  {'-'*90}")
    for p in sorted(data["players"], key=lambda x: x["total_points"], reverse=True):
        bat = p["batting"]["total"] if p["batting"] else 0
        bowl = p["bowling"]["total"] if p["bowling"] else 0
        field = p["fielding"]["total"] if p["fielding"] else 0
        print(f"  {p['name']:25s} {p['team']:22s} {bat:5d} {bowl:5d} {field:5d} {p['total_points']:6d}")
    return True


def test_update_sheet(match_id):
    print(f"\n{'='*60}")
    print(f"[SHEET] Updating sheet for match {match_id}...")
    r = requests.post(f"{BASE}/api/update-sheet", json={"match_id": match_id})
    print(f"[SHEET] Status: {r.status_code}")
    if r.status_code != 200:
        print(f"[SHEET] ERROR: {r.text[:2000]}")
        return False

    data = r.json()
    print(f"  Updated: {len(data['updated_players'])} players")
    print(f"  Unmatched: {len(data['unmatched_players'])} players")
    if data["updated_players"]:
        print(f"\n  {'Scraped':25s} {'Matched':25s} {'Score':>5s} {'Prev':>7s} {'Added':>6s} {'New':>7s}")
        print(f"  {'-'*90}")
        for p in data["updated_players"]:
            print(f"  {p['scraped_name']:25s} {p['matched_name']:25s} {p['match_score']:5d} {p['previous_points']:7.1f} {p['added_points']:6d} {p['new_points']:7.1f}")
    if data["unmatched_players"]:
        print("\n  Unmatched:")
        for u in data["unmatched_players"]:
            print(f"    - {u}")
    return True


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    test_health()

    if step in ("scrape", "all"):
        match_id = test_scrape()
        if match_id is None:
            sys.exit(1)
    else:
        match_id = sys.argv[2] if len(sys.argv) > 2 else None

    if step in ("points", "all") and match_id:
        ok = test_calculate_points(match_id)
        if not ok:
            sys.exit(1)

    if step in ("sheet", "all") and match_id:
        ok = test_update_sheet(match_id)
        if not ok:
            sys.exit(1)

    print(f"\n{'='*60}")
    print("ALL TESTS PASSED" if step == "all" else f"Step '{step}' complete")
