from core.domain.consts import METADATA_KEY_DEPLOYMENT_ENVIRONMENT, METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED
from tests.models import task_run_ser


class TestUsedEnvironment:
    def test_old_field(self):
        run = task_run_ser(metadata={METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED: "environment=production"})
        assert run.used_environment == "production"

    def test_new_field(self):
        run = task_run_ser(metadata={METADATA_KEY_DEPLOYMENT_ENVIRONMENT: "production"})
        assert run.used_environment == "production"

    def test_no_field(self):
        run = task_run_ser()
        assert run.used_environment is None
