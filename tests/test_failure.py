"""Intentional failure test.

This test is SUPPOSED TO FAIL. It exists to prove that the CI pipeline blocks
deployment when a test fails.

The main test suite excludes it with:

    pytest -m "not intentional_failure"

CI runs it on its own to show the deploy step is skipped:

    pytest tests/test_failure.py -m intentional_failure
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.intentional_failure
def test_intentional_failure_blocks_deployment(client: TestClient) -> None:
    """DELIBERATELY FAILS - this is the point of the test.

    Expected CI behaviour:
      1. The test job fails.
      2. The deploy job is skipped because it depends on the test job.
      3. Nothing gets deployed.

    Do not "fix" this test. It is the evidence that the deployment gate works.
    """
    response = client.get("/healthz")
    assert response.status_code == 200

    # This assertion is wrong on purpose. The endpoint returns 200, not 418.
    assert (
        response.status_code == 418
    ), "Intentional failure: proving CI blocks deployment when a test fails."
