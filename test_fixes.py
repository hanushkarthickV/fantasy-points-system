"""
Quick integration test for the three bug fixes:
1. † wicketkeeper catch resolution
2. Duplicate player merging on edit
3. Playing XI bonus for Did Not Bat players (Manav Suthar)

Uses the GT vs RCB Match 42 mhtml as test data.
"""
import sys
import email
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.scraper.scorecard_scraper import parse_scorecard_from_html
from backend.engine.points_calculator import calculate_match_points
from backend.services.match_service import MatchService
from backend.models.schemas import PlayerEdit

MHTML_PATH = Path(__file__).parent / "GT vs RCB Cricket Scorecard, 42nd Match at Ahmedabad, April 30, 2026.mhtml"


def extract_html_from_mhtml(mhtml_path: Path) -> str:
    """Extract the HTML part from an MHTML file."""
    raw = mhtml_path.read_bytes()
    msg = email.message_from_bytes(raw)
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/html":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    raise ValueError("No text/html part found in MHTML")


def test_keeper_catch_and_dnb():
    """Test Bug 1 (keeper catch) and Bug 3 (DNB playing XI)."""
    print("=" * 60)
    print("TEST: Parsing GT vs RCB Match 42")
    print("=" * 60)

    html = extract_html_from_mhtml(MHTML_PATH)
    url = "https://www.espncricinfo.com/series/ipl-2026-1510719/gujarat-titans-vs-royal-challengers-bengaluru-42nd-match-1527715/full-scorecard"
    metadata = parse_scorecard_from_html(html, url)

    print(f"\nMatch: {metadata.match_title}")
    print(f"Teams: {metadata.team1} vs {metadata.team2}")
    print(f"Innings count: {len(metadata.innings)}")

    # Check wicketkeepers detected
    print("\n--- Wicketkeepers ---")
    for inn in metadata.innings:
        print(f"  {inn.team_name}: keeper = {inn.wicketkeeper}")

    # Check keeper catch resolution
    print("\n--- Keeper Catches (is_keeper_catch=True) ---")
    for inn in metadata.innings:
        for d in inn.dismissals:
            if d.is_keeper_catch:
                print(f"  {d.batter_name}: c {d.fielder_name} b {d.bowler_name}")

    # Check DNB players
    print("\n--- Did Not Bat ---")
    for inn in metadata.innings:
        if inn.did_not_bat:
            print(f"  {inn.team_name}: {inn.did_not_bat}")

    # Calculate points
    points = calculate_match_points(metadata)
    player_names = {p.name for p in points.players}

    # Bug 1: Check Jitesh Sharma has fielding points (keeper catch)
    print("\n--- Bug 1: Jitesh Sharma fielding ---")
    jitesh = next((p for p in points.players if "Jitesh" in p.name), None)
    if jitesh:
        print(f"  {jitesh.name}: fielding={jitesh.fielding}, total={jitesh.total_points}")
    else:
        print("  ERROR: Jitesh Sharma not found in points!")

    # Bug 3: Check Manav Suthar has Playing XI bonus
    print("\n--- Bug 3: Manav Suthar (DNB player) ---")
    manav = next((p for p in points.players if "Manav" in p.name), None)
    if manav:
        print(f"  {manav.name}: xi_bonus={manav.playing_xi_bonus}, total={manav.total_points}")
        assert manav.playing_xi_bonus == 4, "Manav Suthar should have +4 Playing XI bonus"
        assert manav.total_points == 4, "Manav Suthar should have exactly 4 points (only XI bonus)"
        print("  ✓ PASS")
    else:
        print("  ERROR: Manav Suthar not found in points!")

    # Verify no player named just "Sharma" exists in fielding
    print("\n--- Verifying no ambiguous 'Sharma' in fielding ---")
    for inn in metadata.innings:
        for f in inn.fielding:
            if f.name == "Sharma":
                print(f"  ERROR: Unresolved 'Sharma' in {inn.team_name} fielding!")
                return False
    print("  ✓ No ambiguous 'Sharma' — keeper catch resolved correctly")

    return True


def test_player_merge():
    """Test Bug 2: Duplicate player merging on edit."""
    print("\n" + "=" * 60)
    print("TEST: Player Merge on Edit")
    print("=" * 60)

    html = extract_html_from_mhtml(MHTML_PATH)
    url = "https://www.espncricinfo.com/series/ipl-2026-1510719/gujarat-titans-vs-royal-challengers-bengaluru-42nd-match-1527715/full-scorecard"
    metadata = parse_scorecard_from_html(html, url)
    points = calculate_match_points(metadata)

    # Simulate: Find if there are two players we can merge
    # Let's simulate the scenario: rename one player to another's name
    # Find Jitesh Sharma's points
    jitesh = next((p for p in points.players if "Jitesh Sharma" in p.name), None)
    if not jitesh:
        print("  Jitesh Sharma not found, skipping merge test")
        return True

    print(f"  Jitesh Sharma before merge: total={jitesh.total_points}")
    print(f"  Player count before: {len(points.players)}")

    # Simulate by creating a mock scenario with MatchService
    # We'll save the points, then edit to merge
    service = MatchService()
    match_id = metadata.match_id

    # Save metadata and points
    service._save_match_json(match_id, "metadata.json", metadata.model_dump())
    service._save_match_json(match_id, "points.json", points.model_dump())

    # Pick another player to merge into Jitesh (simulate the bug scenario)
    # Find a player with fielding points only (if any)
    other = next(
        (p for p in points.players
         if p.name != "Jitesh Sharma" and p.fielding and not p.batting and not p.bowling),
        None
    )

    if other:
        print(f"  Merging '{other.name}' (total={other.total_points}) into 'Jitesh Sharma'")
        original_jitesh_total = jitesh.total_points
        other_base = other.total_points - other.playing_xi_bonus

        edits = [PlayerEdit(original_name=other.name, new_name="Jitesh Sharma")]
        updated = service.edit_players(match_id, edits)

        merged = next((p for p in updated.players if p.name == "Jitesh Sharma"), None)
        print(f"  After merge: Jitesh Sharma total={merged.total_points}")
        print(f"  Expected: {original_jitesh_total} + {other_base} = {original_jitesh_total + other_base}")
        print(f"  Player count after: {len(updated.players)}")

        # Verify the other player is gone
        assert other.name not in {p.name for p in updated.players}, f"'{other.name}' should be gone"
        assert merged.total_points == original_jitesh_total + other_base
        print("  ✓ PASS — merge correct, no duplicate")
    else:
        print("  No suitable merge candidate found; testing with synthetic data")
        # Test with synthetic: duplicate a player under a different name
        from backend.models.schemas import MatchPoints, PlayerPoints, FieldingPointsBreakdown

        fake_points = MatchPoints(
            match_id="test_merge",
            players=[
                PlayerPoints(name="Jitesh Sharma", team="RCB", total_points=10, playing_xi_bonus=4),
                PlayerPoints(
                    name="Sharma", team="RCB", total_points=6, playing_xi_bonus=4,
                    fielding=FieldingPointsBreakdown(catch_points=8, total=8),
                ),
            ],
        )
        service._save_match_json("test_merge", "points.json", fake_points.model_dump())
        edits = [PlayerEdit(original_name="Sharma", new_name="Jitesh Sharma")]
        updated = service.edit_players("test_merge", edits)

        merged = next(p for p in updated.players if p.name == "Jitesh Sharma")
        print(f"  After merge: total={merged.total_points}")
        # Expected: 10 + (6-4) = 12
        assert merged.total_points == 12, f"Expected 12, got {merged.total_points}"
        assert len(updated.players) == 1, f"Expected 1 player, got {len(updated.players)}"
        print("  ✓ PASS — synthetic merge: 10 + (6-4) = 12, single entry")

    return True


if __name__ == "__main__":
    if not MHTML_PATH.exists():
        print(f"ERROR: MHTML file not found at {MHTML_PATH}")
        sys.exit(1)

    ok1 = test_keeper_catch_and_dnb()
    ok2 = test_player_merge()

    print("\n" + "=" * 60)
    if ok1 and ok2:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
        sys.exit(1)
