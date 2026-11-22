from netscope_core.httpprobe import find_block_markers, redact_headers


def test_english_markers_found():
    markers = find_block_markers("<html><title>Access Denied</title> This site has been blocked.</html>")
    assert "access denied" in markers
    assert "this site has been blocked" in markers


def test_persian_markers_found():
    markers = find_block_markers("دسترسی به این سایت مسدود شده است — فیلترینگ")
    assert "فیلترینگ" in markers
    assert "مسدود شده است" in markers
    assert "دسترسی به این سایت" in markers


def test_clean_page_has_no_markers():
    assert find_block_markers("Welcome to the example website.") == []


def test_redaction_replaces_sensitive_values():
    headers = {
        "Authorization": "Bearer secret-token",
        "Cookie": "session=abc",
        "Set-Cookie": "id=1; HttpOnly",
        "Content-Type": "text/html",
        "Server": "example",
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "[redacted]"
    assert redacted["Cookie"] == "[redacted]"
    assert redacted["Set-Cookie"] == "[redacted]"
    assert redacted["Content-Type"] == "text/html"
    assert redacted["Server"] == "example"
    assert "secret-token" not in str(redacted.values())


def test_redaction_is_case_insensitive():
    redacted = redact_headers({"AUTHORIZATION": "Basic xyz"})
    assert redacted["AUTHORIZATION"] == "[redacted]"
