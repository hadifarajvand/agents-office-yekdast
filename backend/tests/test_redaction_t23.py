from app.policy import redact_secrets


def test_prefixed_secret_names_and_url_credentials_are_redacted():
    for text in ("GITHUB_TOKEN=abc123456", "stripe_secret_key: sk_live_zzzzzzzz", "MY_API_KEY=hunter2hunter2",
                 "AWS_ACCESS_KEY_ID=AKIAxxxx", "git clone https://user:pa55w0rd@github.com/x/y"):
        out = redact_secrets(text)
        assert "abc123456" not in out and "sk_live_zzzzzzzz" not in out and "hunter2hunter2" not in out \
            and "pa55w0rd" not in out and "AKIAxxxx" not in out, out
