from datetime import UTC, datetime, timedelta

from tests.conftest import signup

API = "/api/v1"


def minutes_ago(n: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=n)).replace(second=0, microsecond=0).isoformat()


def test_register_login_and_me(client, auth):
    r = client.get(f"{API}/auth/me", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["subscription"]["status"] == "inactive"
    assert body["subscription"]["is_active"] is False


def test_duplicate_registration_and_bad_login(client, auth):
    r = client.post(f"{API}/auth/register", json={"email": "ALICE@example.com", "password": "another-pass"})
    assert r.status_code == 409
    r = client.post(f"{API}/auth/token", data={"username": "alice@example.com", "password": "wrong-pass"})
    assert r.status_code == 401


def test_requires_auth(client):
    assert client.get(f"{API}/devices").status_code == 401


def test_device_requires_subscription(client, auth):
    r = client.post(f"{API}/devices", json={"name": "Watch"}, headers=auth)
    assert r.status_code == 402


def test_mock_checkout_activates_monthly_plan(client, subscribed):
    sub = client.get(f"{API}/billing/subscription", headers=subscribed).json()
    assert sub["plan"] == "basic" and sub["is_active"]
    assert sub["current_period_end"].endswith("Z")  # explicit UTC


def test_plan_device_limit(client, subscribed, device_key):
    r = client.post(f"{API}/devices", json={"name": "Second"}, headers=subscribed)
    assert r.status_code == 403
    client.post(f"{API}/billing/checkout", json={"plan": "pro"}, headers=subscribed)
    r = client.post(f"{API}/devices", json={"name": "Second"}, headers=subscribed)
    assert r.status_code == 201


def test_device_key_not_listed(client, subscribed, device_key):
    devices = client.get(f"{API}/devices", headers=subscribed).json()
    assert len(devices) == 1
    assert "api_key" not in devices[0]
    assert device_key.startswith(devices[0]["api_key_prefix"])


def test_ingest_readings_and_query(client, subscribed, device_key):
    readings = [{"recorded_at": minutes_ago(i), "bpm": 70 + i % 5, "hrv_ms": 42.0, "signal_quality": 0.95} for i in range(10)]
    r = client.post(f"{API}/ingest", json={"readings": readings}, headers={"X-Device-Key": device_key})
    assert r.status_code == 200, r.text
    assert r.json() == {"accepted": 10, "duplicates": 0, "alerts_created": 0}

    # Retrying the same batch is idempotent.
    r = client.post(f"{API}/ingest", json={"readings": readings}, headers={"X-Device-Key": device_key})
    assert r.json()["accepted"] == 0 and r.json()["duplicates"] == 10

    rows = client.get(f"{API}/readings", headers=subscribed).json()
    assert len(rows) == 10
    assert rows[0]["recorded_at"] < rows[-1]["recorded_at"]

    summary = client.get(f"{API}/readings/summary?days=7", headers=subscribed).json()
    assert sum(d["readings"] for d in summary["days"]) == 10
    assert summary["latest"]["bpm"] == 70


def test_summary_ignores_low_signal_samples(client, subscribed, device_key):
    readings = [
        {"recorded_at": minutes_ago(3), "bpm": 70, "signal_quality": 0.9},
        {"recorded_at": minutes_ago(2), "bpm": 31, "signal_quality": 0.2},
    ]
    client.post(f"{API}/ingest", json={"readings": readings}, headers={"X-Device-Key": device_key})
    day = client.get(f"{API}/readings/summary", headers=subscribed).json()["days"][0]
    assert (day["readings"], day["min_bpm"]) == (1, 70)


def test_ingest_rejects_bad_key_and_bad_values(client, device_key):
    r = client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 70}]},
                    headers={"X-Device-Key": "hm_nope"})
    assert r.status_code == 401
    r = client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 400}]},
                    headers={"X-Device-Key": device_key})
    assert r.status_code == 422


def test_alerts_with_cooldown_and_signal_quality(client, subscribed, device_key):
    client.post(f"{API}/billing/checkout", json={"plan": "pro"}, headers=subscribed)
    readings = [
        {"recorded_at": minutes_ago(30), "bpm": 150, "signal_quality": 0.9},  # high -> alert
        {"recorded_at": minutes_ago(29), "bpm": 155, "signal_quality": 0.9},  # within cooldown
        {"recorded_at": minutes_ago(10), "bpm": 160, "signal_quality": 0.9},  # after cooldown -> alert
        {"recorded_at": minutes_ago(5), "bpm": 30, "signal_quality": 0.2},    # poor contact -> ignored
        {"recorded_at": minutes_ago(3), "bpm": 88, "irregular_rhythm": True},  # irregular -> alert
    ]
    r = client.post(f"{API}/ingest", json={"readings": readings}, headers={"X-Device-Key": device_key})
    assert r.json()["alerts_created"] == 3

    alerts = client.get(f"{API}/alerts", headers=subscribed).json()
    assert sorted(a["kind"] for a in alerts) == ["high_hr", "high_hr", "irregular_rhythm"]

    r = client.post(f"{API}/alerts/{alerts[0]['id']}/ack", headers=subscribed)
    assert r.json()["acknowledged"] is True
    assert len(client.get(f"{API}/alerts?unacknowledged_only=true", headers=subscribed).json()) == 2


def test_custom_thresholds(client, subscribed, device_key):
    r = client.patch(f"{API}/auth/me", json={"hr_high_threshold": 100}, headers=subscribed)
    assert r.status_code == 200
    r = client.patch(f"{API}/auth/me", json={"hr_low_threshold": 99, "hr_high_threshold": 90}, headers=subscribed)
    assert r.status_code == 422
    r = client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 105}]},
                    headers={"X-Device-Key": device_key})
    assert r.json()["alerts_created"] == 1


def test_removed_device_and_cancelled_subscription_block_ingest(client, subscribed, device_key):
    sample = {"readings": [{"recorded_at": minutes_ago(1), "bpm": 70}]}
    device_id = client.get(f"{API}/devices", headers=subscribed).json()[0]["id"]

    # Cancel = end of period; still active until then.
    r = client.post(f"{API}/billing/cancel", headers=subscribed)
    assert r.json()["cancel_at_period_end"] is True
    assert client.post(f"{API}/ingest", json=sample, headers={"X-Device-Key": device_key}).status_code == 200

    assert client.delete(f"{API}/devices/{device_id}", headers=subscribed).status_code == 204
    assert client.post(f"{API}/ingest", json=sample, headers={"X-Device-Key": device_key}).status_code == 401


def test_lapsed_subscription_rejects_ingest(client, subscribed, device_key):
    from app.models import Subscription

    with client.session_factory() as db:
        sub = db.query(Subscription).one()
        sub.status = "past_due"
        db.commit()
    r = client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 70}]},
                    headers={"X-Device-Key": device_key})
    assert r.status_code == 402


def test_tenant_isolation(client, subscribed, device_key):
    client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 70}]},
                headers={"X-Device-Key": device_key})
    device_id = client.get(f"{API}/devices", headers=subscribed).json()[0]["id"]

    bob = signup(client, email="bob@example.com")
    assert client.get(f"{API}/readings", headers=bob).json() == []
    assert client.get(f"{API}/readings?device_id={device_id}", headers=bob).status_code == 404
    assert client.delete(f"{API}/devices/{device_id}", headers=bob).status_code == 404


def test_purge_respects_plan_retention(client, subscribed, device_key):
    from app.jobs.purge import purge_expired_readings

    old = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    client.post(f"{API}/ingest", json={"readings": [{"recorded_at": old, "bpm": 70}, {"recorded_at": minutes_ago(1), "bpm": 71}]},
                headers={"X-Device-Key": device_key})
    with client.session_factory() as db:
        assert purge_expired_readings(db) == 1  # basic plan keeps 30 days


def test_basic_plan_has_no_rhythm_alerts(client, subscribed, device_key):
    r = client.post(f"{API}/ingest", json={"readings": [{"recorded_at": minutes_ago(1), "bpm": 80, "irregular_rhythm": True}]},
                    headers={"X-Device-Key": device_key})
    assert r.json()["alerts_created"] == 0
