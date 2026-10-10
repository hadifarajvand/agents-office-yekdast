from app import activity


def test_model_event_carries_the_stage_lead():
    activity.emit("model", "m: 1+1 tokens", job="j1", stage="build", connector="router")
    e = activity._buf[-1]
    assert e["agent"] == "exec-vp-engineering" and e["job"] == "j1"


def test_label_parts_feed_the_agent():
    jid, stg = activity.label_parts("job:abc:security")
    activity.emit("model", "m", job=jid, stage=stg, connector="router")
    assert activity._buf[-1]["agent"] == "sec-compliance"
