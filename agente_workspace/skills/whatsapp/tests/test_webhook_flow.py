from skills.whatsapp.webhook.endpoint import create_app


def test_webhook_text_message_flow(monkeypatch):
    def fake_build_reply(message, router, remote):
        return "respuesta de prueba"

    class FakeClient:
        def send_text(self, to, text):
            return {"ok": True, "to": to, "text": text}

    monkeypatch.setattr("skills.whatsapp.webhook.endpoint._build_reply", fake_build_reply)
    app = create_app(wa_client=FakeClient())
    client = app.test_client()

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "12345",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json["ok"] is True
    assert resp.json["reply"] == "respuesta de prueba"
    assert resp.json["outbound"]["ok"] is True
