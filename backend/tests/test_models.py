from app.models import HAIKU_MODEL_ID, MODEL_KEYS, effort_for, model_for, model_id


def test_haiku_not_in_public_model_keys():
    assert "haiku" not in MODEL_KEYS
    assert HAIKU_MODEL_ID  # resolved, but never selectable via task/routine/agent/office


def test_model_precedence_task_beats_routine_beats_agent_beats_office():
    assert model_for("opus", "fable", "sonnet", "sonnet")["model"] == "opus"
    assert model_for(None, "fable", "sonnet", "sonnet")["model"] == "fable"
    assert model_for(None, None, "sonnet", "fable")["model"] == "sonnet"
    assert model_for(None, None, None, "fable")["model"] == "fable"
    assert model_for(None, None, None, None)["model"] == "sonnet"


def test_effort_precedence_and_model_default():
    assert effort_for("high", None, None, None, "opus")["effort"] == "high"
    assert effort_for(None, None, None, None, "opus")["effort"] == "high"
    assert effort_for(None, None, None, None, "sonnet")["effort"] is None


def test_model_id_resolves_env_backed_id():
    assert model_id("sonnet")
    assert model_id("opus")
