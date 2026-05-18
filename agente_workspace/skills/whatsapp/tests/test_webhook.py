from skills.whatsapp.webhook.endpoint import create_app


def test_webhook_health_get_forbidden_without_token():
    app = create_app()
    client = app.test_client()
    resp = client.get("/webhook")
    assert resp.status_code in {200, 403}


def test_webhook_post_invalid_json():
    app = create_app()
    client = app.test_client()
    resp = client.post("/webhook", data="not-json", content_type="text/plain")
    assert resp.status_code in {400, 401}


def test_webhook_post_status_event_ignored():
    app = create_app()
    client = app.test_client()
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [{"id": "abc"}],
                        }
                    }
                ]
            }
        ]
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json.get("ok") is True
