"""The client-job pipeline: intake -> verify -> scope -> build -> security -> preview ->
exposure -> handoff. Each stage is worked by agents, reviewed by the lead of the
department that owns it, and gated by that lead's approval (plus the owner for the
verdict, the handoff, and exposure)."""
