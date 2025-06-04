import os

METADATA_KEY_REQUESTED_ITERATION = "workflowai.iteration"
METADATA_KEY_DEPLOYMENT_ENVIRONMENT = "workflowai.deployment.env"
# When the "latest" version of a model is used, we store the model used in the metadata
METADATA_KEY_USED_MODEL = "workflowai.model"
# The provider that is used when the provider was not specified
METADATA_KEY_USED_PROVIDERS = "workflowai.providers"
METADATA_KEY_PROVIDER_NAME = "workflowai.provider"
METADATA_KEY_INFERENCE_SECONDS = "workflowai.inference_seconds"
METADATA_KEY_FILE_DOWNLOAD_SECONDS = "workflowai.file_download_seconds"
METADATA_KEY_DEPLOYMENT_ENVIRONMENT_DEPRECATED = "used_alias"
METADATA_KEY_INTEGRATION = "workflowai.integration"


INPUT_KEY_MESSAGES = "workflowai.messages"
INPUT_KEY_MESSAGES_DEPRECATED = "workflowai.replies"
"""
When using the OpenAI proxy and input variables, the extra messages passed
are appended to the end of the messages list.
This is done by adding a key to the input with this value.
"""

WORKFLOWAI_RUN_URL = os.getenv("WORKFLOWAI_API_URL", "https://run.workflowai.com")

IMAGE_REF_NAME = "Image"
FILE_REF_NAME = "File"
AUDIO_REF_NAME = "Audio"
PDF_REF_NAME = "PDF"

# All possible defs that represent files
FILE_DEFS = {IMAGE_REF_NAME, FILE_REF_NAME, AUDIO_REF_NAME, PDF_REF_NAME}

WORKFLOWAI_APP_URL = os.getenv("WORKFLOWAI_APP_URL", "https://workflowai.com")

ENV_NAME = os.getenv("ENV_NAME", "local")
