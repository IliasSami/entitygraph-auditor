"""Security tests for SSRF protections (PRD §18)."""

import pytest
from ega_parsers import SSRFException, validate_url_safety


def test_ssrf_blocks_localhost():
    with pytest.raises(SSRFException):
        validate_url_safety("http://127.0.0.1:8000/internal")


def test_ssrf_blocks_private_ip():
    with pytest.raises(SSRFException):
        validate_url_safety("http://192.168.1.100/admin")
    with pytest.raises(SSRFException):
        validate_url_safety("http://10.0.0.5/api")


def test_ssrf_blocks_cloud_metadata():
    with pytest.raises(SSRFException):
        validate_url_safety("http://169.254.169.254/latest/meta-data/")


def test_ssrf_blocks_invalid_scheme():
    with pytest.raises(SSRFException):
        validate_url_safety("file:///etc/passwd")
    with pytest.raises(SSRFException):
        validate_url_safety("gopher://localhost:11211")
