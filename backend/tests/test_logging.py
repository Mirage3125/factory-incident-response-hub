import logging

from factory_hub.logging import SensitiveDataFilter, mask_sensitive_value


def test_mask_sensitive_value_keeps_edges_only():
    masked = mask_sensitive_value("stage-1-secret-token")

    assert masked.startswith("stag")
    assert masked.endswith("oken")
    assert "stage-1-secret-token" not in masked


def test_sensitive_data_filter_masks_token_password_and_resume_url():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=stage-1-secret-token password=secret resume_url=http://n8n/resume/abc",
        args=(),
        exc_info=None,
    )

    SensitiveDataFilter().filter(record)

    message = record.getMessage()
    assert "stage-1-secret-token" not in message
    assert "password=secret" not in message
    assert "http://n8n/resume/abc" not in message
    assert "token=stag" in message
    assert "oken" in message
    assert "password=se****" in message
    assert "resume_url=http" in message
    assert "/abc" in message
