import pytest

from core.domain.consts import METADATA_KEY_DEPLOYMENT_ENVIRONMENT, METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED
from tests.models import task_run_ser


class TestUsedEnvironment:
    def test_old_field(self):
        run = task_run_ser(metadata={METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED: "environment=production"})
        assert run.used_environment == "production"

    def test_new_field(self):
        run = task_run_ser(metadata={METADATA_KEY_DEPLOYMENT_ENVIRONMENT: "production"})
        assert run.used_environment == "production"

    @pytest.mark.parametrize(
        "metadata",
        [
            pytest.param(None, id="no_metadata"),
            pytest.param({}, id="empty_metadata"),
            pytest.param({"bla": "bla"}, id="other_metadata"),
            pytest.param({METADATA_KEY_DEPLOYMENT_ENVIRONMENT: "pro"}, id="invalid_metadata"),
            pytest.param({METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED: "pri"}, id="invalid_metadata_with_old_key"),
        ],
    )
    def test_no_or_invalid_field(self, metadata: dict[str, str] | None):
        run = task_run_ser(metadata=metadata)
        assert run.used_environment is None


class TestFilteredMetadata:
    def test_no_metadata(self):
        run = task_run_ser()
        assert run.filtered_metadata is None

    def test_metadata(self):
        run = task_run_ser(
            metadata={
                "bla": "bla",
                "workflowai.test": "test",
                METADATA_KEY_DEPLOYMENT_ENVIRONMENT: "production",
            },
        )
        assert run.filtered_metadata == {"bla": "bla"}
