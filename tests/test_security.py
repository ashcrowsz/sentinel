from sentinel.security import compute_signature, verify_signature

SECRET = "s3cret"
BODY = b'{"action":"opened"}'


def test_valid_signature_passes() -> None:
    assert verify_signature(SECRET, BODY, compute_signature(SECRET, BODY))


def test_wrong_secret_fails() -> None:
    assert not verify_signature(SECRET, BODY, compute_signature("other", BODY))


def test_tampered_body_fails() -> None:
    sig = compute_signature(SECRET, BODY)
    assert not verify_signature(SECRET, BODY + b" ", sig)


def test_missing_or_malformed_header_fails() -> None:
    assert not verify_signature(SECRET, BODY, None)
    assert not verify_signature(SECRET, BODY, "sha1=deadbeef")
