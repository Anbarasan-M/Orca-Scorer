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
