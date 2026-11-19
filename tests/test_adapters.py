from gtmharness.adapters import hubspot, salesforce


def test_hubspot_missing_sdk_raises(tmp_path):
    try:
        hubspot._client({"token": "x"})
    except RuntimeError as e:
        assert "gtmharness[hubspot]" in str(e)
        return
    assert False, "expected RuntimeError (SDK not installed in test env)"


def test_hubspot_missing_token_raises():
    try:
        hubspot._client({})
    except RuntimeError as e:
        assert "token" in str(e)
        return
    assert False, "expected RuntimeError"


def test_salesforce_missing_sdk_raises():
    try:
        salesforce._client({"username": "u", "password": "p", "security_token": "t"})
    except RuntimeError as e:
        assert "gtmharness[salesforce]" in str(e)
        return
    assert False, "expected RuntimeError (SDK not installed in test env)"


def test_salesforce_missing_creds_raises():
    try:
        salesforce._client({"username": "u"})
    except RuntimeError as e:
        assert "security_token" in str(e)
        return
    assert False, "expected RuntimeError"
