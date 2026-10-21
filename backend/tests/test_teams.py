"""Tests for /teams endpoints."""


def test_create_and_get_team(client):
    res = client.post("/teams", json={"name": "Kolkata Knight Riders", "short_name": "kkr"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Kolkata Knight Riders"
    assert data["short_name"] == "KKR"  # Normalized to uppercase
    team_id = data["id"]

    get_res = client.get(f"/teams/{team_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Kolkata Knight Riders"


def test_team_duplicate_name_conflict(client):
    client.post("/teams", json={"name": "Royal Challengers", "short_name": "RCB"})
    res = client.post("/teams", json={"name": "Royal Challengers", "short_name": "RC2"})
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()
