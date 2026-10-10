"""Persist GitHub activity and disclose the API's bounded event history."""


def audit_events(store, github):
    """Record new events while detecting a lost pagination boundary.

    How:
    1. Read every available page of GitHub's bounded activity feed.
    2. Detect whether the previous newest event remains in that history.
    3. Store new event IDs and the coverage result in one transaction.
    """
    events = [event for page in github.pages("events?per_page=100") for event in page]
    previous = store.get("state", "events")
    ids = {event["id"] for event in events}
    gap = bool(previous and previous.get("newest_id") and previous["newest_id"] not in ids)
    new = [event for event in events if store.get("event", event["id"]) is None]
    report = {
        "new_events": [{"id": e["id"], "type": e["type"], "created_at": e["created_at"]} for e in new],
        "initial_inventory": previous is None,
        "coverage_gap": gap,
        "note": "GitHub activity history is limited to 300 events / 90 days; CI and PR inventories are audited separately.",
    }
    with store.transaction():
        for event in new:
            store.put("event", event["id"], event)
        store.put("state", "events", {"newest_id": events[0]["id"] if events else None})
        store.record("events", report)
    return report
