"""Tests for scorecard and statistics endpoints."""

from tests.test_scoring import _setup_match_and_innings


def test_innings_and_match_scorecard(client):
    env = _setup_match_and_innings(client)
    inn_id = env["innings"]["id"]
    match_id = env["match"]["id"]

    # Bowl a single and a catch
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 1,
        },
    )
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b2"],
            "non_striker_id": env["b1"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 0,
            "wicket": {
                "player_out_id": env["b2"],
                "wicket_type": "CAUGHT",
                "fielder_id": env["fielder"],
            },
        },
    )

    # Check innings scorecard
    sc = client.get(f"/innings/{inn_id}/scorecard").json()
    assert sc["total_runs"] == 1
    assert sc["wickets_lost"] == 1
    assert sc["overs"] == "0.2"

    # Check dismissals text
    b2_entry = next(b for b in sc["batting"] if b["player_id"] == env["b2"])
    assert "c Fielder Safe b Bowler Fast" in b2_entry["dismissal_text"]

    # Check match scorecard
    m_sc = client.get(f"/matches/{match_id}/scorecard").json()
    assert len(m_sc["innings"]) == 1

    # Check player statistics
    p_stats = client.get(f"/players/{env['b1']}/statistics").json()
    assert p_stats["batting"]["runs"] >= 1
    assert p_stats["batting"]["innings"] >= 1


def test_fall_of_wickets_and_partnerships(client):
    env = _setup_match_and_innings(client)
    inn_id = env["innings"]["id"]

    # Ball 1: b1 hits 2 runs off bat
    r1 = client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 2,
        },
    ).json()
    assert r1["current_partnership"] is not None
    assert r1["current_partnership"]["runs"] == 2
    assert r1["current_partnership"]["balls"] == 1

    # Ball 2: b1 takes a single (strike rotates)
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 1,
        },
    )

    # Ball 3: b2 is bowled (score is 3, 0.3 overs)
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b2"],
            "non_striker_id": env["b1"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 0,
            "wicket": {
                "player_out_id": env["b2"],
                "wicket_type": "BOWLED",
            },
        },
    )

    # Inspect scorecard after 1st wicket
    sc = client.get(f"/innings/{inn_id}/scorecard").json()
    assert len(sc["fall_of_wickets"]) == 1
    fow1 = sc["fall_of_wickets"][0]
    assert fow1["wicket_number"] == 1
    assert fow1["score"] == 3
    assert fow1["overs"] == "0.3"
    assert fow1["player_id"] == env["b2"]

    # New batter b3 comes in
    # Ball 4: b1 hits 4 runs
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b3"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 4,
        },
    )

    # Ball 5: Wide (+1 run)
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b3"],
            "bowler_id": env["bowler"],
            "wide_runs": 1,
        },
    )

    # Ball 6: b1 hits 1 run
    r6 = client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b3"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 1,
        },
    ).json()

    # Active partnership now: 4 (bat) + 1 (wide) + 1 (bat) = 6 runs, 2 balls faced
    p = r6["current_partnership"]
    assert p is not None
    assert p["runs"] == 6
    assert p["balls"] == 2

    # Ball 7: b3 is run out
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b3"],
            "non_striker_id": env["b1"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 0,
            "wicket": {
                "player_out_id": env["b3"],
                "wicket_type": "RUN_OUT",
                "fielder_id": env["fielder"],
            },
        },
    )

    # Check updated scorecard fall of wickets
    sc2 = client.get(f"/innings/{inn_id}/scorecard").json()
    assert len(sc2["fall_of_wickets"]) == 2
    fow2 = sc2["fall_of_wickets"][1]
    assert fow2["wicket_number"] == 2
    assert fow2["score"] == 9  # 3 + 6
    assert fow2["overs"] == "1.0"  # 6 legal balls bowled = 1.0 overs
    assert fow2["player_id"] == env["b3"]
