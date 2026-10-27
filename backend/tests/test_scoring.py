"""Tests for the ball-by-ball scoring engine and delivery undo."""

from datetime import datetime, timezone


def _setup_match_and_innings(client):
    t1 = client.post("/teams", json={"name": "Orcas XI", "short_name": "OXI"}).json()
    t2 = client.post("/teams", json={"name": "Warriors XI", "short_name": "WXI"}).json()

    # Create players and add to squads
    b1 = client.post("/players", json={"name": "Batter One"}).json()
    b2 = client.post("/players", json={"name": "Batter Two"}).json()
    b3 = client.post("/players", json={"name": "Batter Three"}).json()
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": b1["id"]})
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": b2["id"]})
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": b3["id"]})

    bowler = client.post("/players", json={"name": "Bowler Fast"}).json()
    fielder = client.post("/players", json={"name": "Fielder Safe"}).json()
    client.post(f"/teams/{t2['id']}/squad", json={"player_id": bowler["id"]})
    client.post(f"/teams/{t2['id']}/squad", json={"player_id": fielder["id"]})

    # Create match and nominate match players
    match = client.post(
        "/matches",
        json={
            "team1_id": t1["id"],
            "team2_id": t2["id"],
            "match_date": datetime.now(timezone.utc).isoformat(),
            "format": "T20",
        },
    ).json()

    client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t1["id"],
            "players": [
                {"player_id": b1["id"], "batting_position": 1},
                {"player_id": b2["id"], "batting_position": 2},
                {"player_id": b3["id"], "batting_position": 3},
            ],
        },
    )
    client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t2["id"],
            "players": [
                {"player_id": bowler["id"], "batting_position": 1},
                {"player_id": fielder["id"], "batting_position": 2},
            ],
        },
    )

    # Start innings
    innings = client.post(
        "/innings",
        json={
            "match_id": match["id"],
            "innings_number": 1,
            "batting_team_id": t1["id"],
            "bowling_team_id": t2["id"],
        },
    ).json()

    return {
        "match": match,
        "innings": innings,
        "b1": b1["id"],
        "b2": b2["id"],
        "b3": b3["id"],
        "bowler": bowler["id"],
        "fielder": fielder["id"],
    }


def test_scoring_flow_and_strike_rotation(client):
    env = _setup_match_and_innings(client)
    inn_id = env["innings"]["id"]

    # Ball 1: Single -> strike rotates from b1 to b2
    r1 = client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 1,
        },
    ).json()
    assert r1["current_score"] == 1
    assert r1["overs_completed_display"] == "0.1"
    assert r1["next_striker_id"] == env["b2"]
    assert r1["next_non_striker_id"] == env["b1"]

    # Ball 2: Wide -> score increases to 2, over does NOT advance (remains 0.1)
    r2 = client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b2"],
            "non_striker_id": env["b1"],
            "bowler_id": env["bowler"],
            "wide_runs": 1,
        },
    ).json()
    assert r2["current_score"] == 2
    assert r2["overs_completed_display"] == "0.1"
    assert r2["delivery"]["is_legal"] is False

    # Ball 3: No-ball hit for six -> total 7 runs, bowler conceded 7
    r3 = client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b2"],
            "non_striker_id": env["b1"],
            "bowler_id": env["bowler"],
            "no_ball_runs": 1,
            "runs_off_bat": 6,
        },
    ).json()
    assert r3["delivery"]["total_runs"] == 7
    assert r3["delivery"]["runs_conceded"] == 7
    assert r3["current_score"] == 9
    assert r3["overs_completed_display"] == "0.1"


def test_undo_last_delivery(client):
    env = _setup_match_and_innings(client)
    inn_id = env["innings"]["id"]

    # Score two balls
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 4,
        },
    )
    client.post(
        f"/innings/{inn_id}/deliveries",
        json={
            "batter_id": env["b1"],
            "non_striker_id": env["b2"],
            "bowler_id": env["bowler"],
            "runs_off_bat": 6,
        },
    )

    deliveries_before = client.get(f"/innings/{inn_id}/deliveries").json()
    assert len(deliveries_before) == 2

    # Undo
    undo_res = client.delete(f"/innings/{inn_id}/deliveries/last")
    assert undo_res.status_code == 200
    assert undo_res.json()["runs_off_bat"] == 6

    deliveries_after = client.get(f"/innings/{inn_id}/deliveries").json()
    assert len(deliveries_after) == 1
    assert deliveries_after[0]["runs_off_bat"] == 4


def test_second_innings_and_match_resolution(client):
    t1 = client.post("/teams", json={"name": "Orcas Alpha", "short_name": "OA"}).json()
    t2 = client.post("/teams", json={"name": "Warriors Beta", "short_name": "WB"}).json()

    b1 = client.post("/players", json={"name": "Alpha One"}).json()
    b2 = client.post("/players", json={"name": "Alpha Two"}).json()
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": b1["id"]})
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": b2["id"]})

    bowler = client.post("/players", json={"name": "Beta Bowler"}).json()
    fielder = client.post("/players", json={"name": "Beta Fielder"}).json()
    client.post(f"/teams/{t2['id']}/squad", json={"player_id": bowler["id"]})
    client.post(f"/teams/{t2['id']}/squad", json={"player_id": fielder["id"]})

    match = client.post(
        "/matches",
        json={
            "team1_id": t1["id"],
            "team2_id": t2["id"],
            "match_date": datetime.now(timezone.utc).isoformat(),
            "format": "CUSTOM",
            "total_overs": 1,
        },
    ).json()

    client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t1["id"],
            "players": [
                {"player_id": b1["id"], "batting_position": 1},
                {"player_id": b2["id"], "batting_position": 2},
            ],
        },
    )
    client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t2["id"],
            "players": [
                {"player_id": bowler["id"], "batting_position": 1},
                {"player_id": fielder["id"], "batting_position": 2},
            ],
        },
    )

    # Start 1-over innings 1
    inn1 = client.post(
        "/innings",
        json={
            "match_id": match["id"],
            "innings_number": 1,
            "batting_team_id": t1["id"],
            "bowling_team_id": t2["id"],
            "max_overs": 1,
        },
    ).json()

    inn1_id = inn1["id"]
    match_id = match["id"]

    # Bowl 6 legal balls in Innings 1 (6 singles = 6 runs)
    for _ in range(6):
        client.post(
            f"/innings/{inn1_id}/deliveries",
            json={
                "batter_id": b1["id"],
                "non_striker_id": b2["id"],
                "bowler_id": bowler["id"],
                "runs_off_bat": 1,
            },
        )

    # Innings 1 should be completed after 1 over (6 balls)
    inn1_check = client.get(f"/innings/{inn1_id}").json()
    assert inn1_check["status"] == "COMPLETED"

    # Start Innings 2 via next innings endpoint
    next_res = client.post(f"/matches/{match_id}/innings/next")
    assert next_res.status_code == 201
    inn2 = next_res.json()
    assert inn2["innings_number"] == 2
    assert inn2["target_runs"] == 7  # 6 runs + 1
    assert inn2["batting_team_id"] == t2["id"]

    # Team 2 bats: hits a six and a two (8 runs total -> target 7 chased!)
    client.post(
        f"/innings/{inn2['id']}/deliveries",
        json={
            "batter_id": bowler["id"],
            "non_striker_id": fielder["id"],
            "bowler_id": b1["id"],
            "runs_off_bat": 6,
        },
    )
    r_win = client.post(
        f"/innings/{inn2['id']}/deliveries",
        json={
            "batter_id": bowler["id"],
            "non_striker_id": fielder["id"],
            "bowler_id": b1["id"],
            "runs_off_bat": 2,
        },
    ).json()

    assert r_win["is_innings_complete"] is True

    # Verify match completed & winner resolved!
    match_data = client.get(f"/matches/{match_id}").json()
    assert match_data["status"] == "COMPLETED"
    assert match_data["result_type"] == "WIN"
    assert match_data["winner_team_id"] == t2["id"]

    # Verify scorecard summary
    scorecard = client.get(f"/matches/{match_id}/scorecard").json()
    assert "won by" in scorecard["summary_text"].lower()

    # Test Undo reverts match back to LIVE!
    client.delete(f"/innings/{inn2['id']}/deliveries/last")
    match_reopened = client.get(f"/matches/{match_id}").json()
    assert match_reopened["status"] == "LIVE"
    assert match_reopened["winner_team_id"] is None
