"""Tests for /matches endpoints and cross-table validation."""

from datetime import datetime, timezone


def test_create_match_validation(client):
    # Setup two teams
    t1 = client.post("/teams", json={"name": "Team Alpha", "short_name": "ALP"}).json()
    t2 = client.post("/teams", json={"name": "Team Beta", "short_name": "BET"}).json()

    # Reject same team
    bad_res = client.post(
        "/matches",
        json={
            "team1_id": t1["id"],
            "team2_id": t1["id"],
            "match_date": datetime.now(timezone.utc).isoformat(),
            "format": "T20",
        },
    )
    assert bad_res.status_code == 422

    # Successfully create match
    good_res = client.post(
        "/matches",
        json={
            "team1_id": t1["id"],
            "team2_id": t2["id"],
            "match_date": datetime.now(timezone.utc).isoformat(),
            "venue": "Wankhede Stadium",
            "format": "T20",
        },
    )
    assert good_res.status_code == 201
    match = good_res.json()
    assert match["total_overs"] == 20  # Inferred
    assert match["team1"]["name"] == "Team Alpha"
    assert match["team2"]["name"] == "Team Beta"


def test_toss_and_squad_validation(client):
    t1 = client.post("/teams", json={"name": "Sunrisers", "short_name": "SRH"}).json()
    t2 = client.post("/teams", json={"name": "Capitals", "short_name": "DC"}).json()

    # Add players to SRH
    p1 = client.post("/players", json={"name": "Travis Head"}).json()
    p2 = client.post("/players", json={"name": "Abhishek Sharma"}).json()
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": p1["id"]})
    client.post(f"/teams/{t1['id']}/squad", json={"player_id": p2["id"]})

    # Outsider player
    p_outsider = client.post("/players", json={"name": "Rishabh Pant"}).json()

    # Create match
    match = client.post(
        "/matches",
        json={
            "team1_id": t1["id"],
            "team2_id": t2["id"],
            "match_date": datetime.now(timezone.utc).isoformat(),
            "format": "T20",
        },
    ).json()

    # Reject outsider toss winner
    bad_toss = client.patch(
        f"/matches/{match['id']}",
        json={"toss_winner_id": 99999, "toss_decision": "BAT"},
    )
    assert bad_toss.status_code == 400

    # Record valid toss
    good_toss = client.patch(
        f"/matches/{match['id']}",
        json={"toss_winner_id": t1["id"], "toss_decision": "BAT", "status": "LIVE"},
    )
    assert good_toss.status_code == 200
    assert good_toss.json()["toss_winner"]["name"] == "Sunrisers"

    # Reject naming outsider player in squad
    bad_squad = client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t1["id"],
            "players": [{"player_id": p_outsider["id"], "batting_position": 1}],
        },
    )
    assert bad_squad.status_code == 400
    assert "not active members" in bad_squad.json()["detail"]

    # Name valid squad
    good_squad = client.post(
        f"/matches/{match['id']}/players",
        json={
            "team_id": t1["id"],
            "players": [
                {"player_id": p1["id"], "batting_position": 1, "is_captain": True},
                {"player_id": p2["id"], "batting_position": 2, "is_wicket_keeper": True},
            ],
        },
    )
    assert good_squad.status_code == 200
    assert len(good_squad.json()) == 2
