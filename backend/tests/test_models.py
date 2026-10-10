from app.models import HAIKU_MODEL_ID, MODEL_KEYS, effort_for, model_for, model_id


def test_haiku_is_the_office_default_model():
    assert "haiku" in MODEL_KEYS
    assert HAIKU_MODEL_ID
    assert model_for(None, None, None, None)["model"] == "haiku"


def test_model_precedence_task_beats_routine_beats_agent_beats_office():
    assert model_for("opus", "fable", "sonnet", "sonnet")["model"] == "opus"
    assert model_for(None, "fable", "sonnet", "sonnet")["model"] == "fable"
    assert model_for(None, None, "sonnet", "fable")["model"] == "sonnet"
    assert model_for(None, None, None, "fable")["model"] == "fable"
    assert model_for(None, None, None, None)["model"] == "haiku"


def test_effort_precedence_and_model_default():
    assert effort_for("high", None, None, None, "opus")["effort"] == "high"
    assert effort_for(None, None, None, None, "opus")["effort"] == "high"
    assert effort_for(None, None, None, None, "sonnet")["effort"] is None
    assert effort_for(None, None, None, None, "haiku")["effort"] is None


def test_model_id_resolves_env_backed_id():
    assert model_id("sonnet")
    assert model_id("opus")
    assert model_id("haiku") == HAIKU_MODEL_ID


def test_any_router_id_passes_through():
    from app.models import is_router_id, model_for, model_id, norm_model
    assert is_router_id("oc/mimo-v2.5-free") and is_router_id("kr/glm-5")
    assert not is_router_id("sonnet-evil") and not is_router_id("a b/c") and not is_router_id("../x/y;rm")
    assert norm_model("oc/Mimo-V2.5-Free") == "oc/Mimo-V2.5-Free"
    assert model_id("oc/mimo-v2.5-free") == "oc/mimo-v2.5-free"
    assert model_for(task="oc/mimo-v2.5-free")["model"] == "oc/mimo-v2.5-free"
    assert norm_model("nonsense") is None
