"""Tests for VerificationEngine."""
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from webcmd.core.verification import VerificationEngine, AssertionSpec
from webcmd.state.enums import AssertionType, VerificationStatus
from webcmd.workers.types import ObservationRecord


@pytest.fixture
def engine() -> VerificationEngine:
    return VerificationEngine()


def create_observation(obs_type: str, data: dict) -> ObservationRecord:
    return ObservationRecord(
        observation_id=uuid4(),
        worker_id=uuid4(),
        step_id=uuid4(),
        observation_type=obs_type,
        data=data
    )


@pytest.mark.asyncio
async def test_empty_assertions_pass(engine: VerificationEngine):
    result = await engine.evaluate([], [])
    assert result.status == VerificationStatus.PASS
    assert result.confidence == 1.0
    assert result.passed_count == 0


@pytest.mark.asyncio
async def test_url_equals_pass(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.URL_EQUALS,
        expected={"url": "https://example.com"}
    )
    obs = create_observation("url", {"url": "https://example.com"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.PASS
    assert result.assertions[0].passed is True


@pytest.mark.asyncio
async def test_url_equals_fail(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.URL_EQUALS,
        expected={"url": "https://example.com"}
    )
    obs = create_observation("url", {"url": "https://wrong.com"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.FAIL
    assert result.assertions[0].passed is False


@pytest.mark.asyncio
async def test_url_contains(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.URL_CONTAINS,
        expected={"substring": "example"}
    )
    obs = create_observation("url", {"url": "https://www.example.com/page"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.PASS
    assert result.assertions[0].passed is True


@pytest.mark.asyncio
async def test_dom_contains_pass(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.DOM_CONTAINS,
        expected={"text": "Welcome"}
    )
    obs = create_observation("dom_snapshot", {"content": "<html><body>Welcome to WebCMD</body></html>"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.PASS
    assert result.assertions[0].passed is True


@pytest.mark.asyncio
async def test_dom_contains_fail(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.DOM_CONTAINS,
        expected={"text": "Goodbye"}
    )
    obs = create_observation("dom_snapshot", {"content": "<html><body>Welcome to WebCMD</body></html>"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.FAIL
    assert result.assertions[0].passed is False


@pytest.mark.asyncio
async def test_text_matches_regex(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.TEXT_MATCHES,
        expected={"pattern": r"\b\d{3}-\d{2}-\d{4}\b"}
    )
    obs = create_observation("page_content", {"content": "SSN: 123-45-6789 is confidential"})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.PASS
    assert result.assertions[0].passed is True


@pytest.mark.asyncio
async def test_file_exists(engine: VerificationEngine):
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"test")
        tf_path = tf.name

    try:
        spec = AssertionSpec(
            assertion_type=AssertionType.FILE_EXISTS,
            expected={"path": tf_path}
        )
        result = await engine.evaluate([spec], [])
        assert result.status == VerificationStatus.PASS
        assert result.assertions[0].passed is True
    finally:
        os.remove(tf_path)


@pytest.mark.asyncio
async def test_file_not_exists(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.FILE_EXISTS,
        expected={"path": "/path/to/nonexistent/file.txt"}
    )
    result = await engine.evaluate([spec], [])
    assert result.status == VerificationStatus.FAIL
    assert result.assertions[0].passed is False


@pytest.mark.asyncio
async def test_http_status(engine: VerificationEngine):
    spec = AssertionSpec(
        assertion_type=AssertionType.HTTP_STATUS,
        expected={"status_code": 201}
    )
    obs = create_observation("http_response", {"status_code": 201})
    
    result = await engine.evaluate([spec], [obs])
    assert result.status == VerificationStatus.PASS
    assert result.assertions[0].passed is True


@pytest.mark.asyncio
async def test_multiple_assertions_all_pass(engine: VerificationEngine):
    specs = [
        AssertionSpec(assertion_type=AssertionType.HTTP_STATUS, expected={"status_code": 200}),
        AssertionSpec(assertion_type=AssertionType.URL_EQUALS, expected={"url": "https://ok.com"})
    ]
    obs = [
        create_observation("http_response", {"status_code": 200}),
        create_observation("url", {"url": "https://ok.com"})
    ]
    
    result = await engine.evaluate(specs, obs)
    assert result.status == VerificationStatus.PASS
    assert result.passed_count == 2
    assert result.total_count == 2


@pytest.mark.asyncio
async def test_multiple_assertions_partial(engine: VerificationEngine):
    specs = [
        AssertionSpec(assertion_type=AssertionType.HTTP_STATUS, expected={"status_code": 200}),
        AssertionSpec(assertion_type=AssertionType.URL_EQUALS, expected={"url": "https://ok.com"}, required=False)
    ]
    obs = [
        create_observation("http_response", {"status_code": 200}),
        create_observation("url", {"url": "https://wrong.com"})
    ]
    
    result = await engine.evaluate(specs, obs)
    assert result.status == VerificationStatus.PARTIAL
    assert result.passed_count == 1
    assert result.failed_count == 1


@pytest.mark.asyncio
async def test_required_vs_optional(engine: VerificationEngine):
    specs = [
        AssertionSpec(assertion_type=AssertionType.HTTP_STATUS, expected={"status_code": 200}, required=False),
        AssertionSpec(assertion_type=AssertionType.URL_EQUALS, expected={"url": "https://ok.com"}, required=True)
    ]
    obs = [
        create_observation("http_response", {"status_code": 404}),
        create_observation("url", {"url": "https://wrong.com"})
    ]
    
    result = await engine.evaluate(specs, obs)
    assert result.status == VerificationStatus.FAIL
