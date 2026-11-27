def test_analytics_disabled(app, client):
    app.config["ENABLE_ANALYTICS"] = False
    response = client.get("/api/analytics")
    assert response.status_code == 404
    assert response.get_json()["error"] == "feature_disabled"


def test_analytics_enabled_keeps_authentication(app, client):
    app.config["ENABLE_ANALYTICS"] = True
    response = client.get("/api/analytics")
    assert response.status_code == 401
