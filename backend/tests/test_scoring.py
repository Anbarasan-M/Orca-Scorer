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
