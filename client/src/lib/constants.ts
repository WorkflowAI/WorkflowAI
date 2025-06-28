export const API_URL = process.env.NEXT_PUBLIC_WORKFLOWAI_API_URL ?? 'https://api.workflowai.com';

export const BACKEND_API_URL = process.env.WORKFLOWAI_API_URL ?? API_URL;

export const PROD_RUN_URL = 'https://run.workflowai.com';

export const RUN_URL = process.env.NEXT_PUBLIC_WORKFLOWAI_RUN_URL ?? API_URL.replace('https://api.', 'https://run.');

export const CONTACT_SALES_TYPEFORM_URL = 'https://workflowai.typeform.com/to/SmpNDv6Z';

export const WORKFLOW_AI_USERNAME = 'WorkflowAI';

export const IMAGE_REF_NAME = 'Image';
export const AUDIO_REF_NAME = 'Audio';
export const PDF_REF_NAME = 'PDF';
export const FILE_REF_NAME = 'File';
export const FILE_REF_NAMES = [IMAGE_REF_NAME, AUDIO_REF_NAME, PDF_REF_NAME, FILE_REF_NAME];

export const LEGACY_TASK_RUN_RUN_BY_METADATA_KEY = 'runBy';
export const WORKFLOW_AI_METADATA_PREFIX = 'workflowai.';

export const DOCUMENT_MIME_TYPES = ['application/pdf', 'text/csv', 'text/plain'];

export const IMAGE_MIME_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif'];

/**
 * If set the authentication is disabled entirely
 */
export const DISABLE_AUTHENTICATION = process.env.NEXT_PUBLIC_DISABLE_AUTHENTICATION === 'true';

/**
 * If set the tenant is hardcoded and organizations are not used on clerk
 */
export const HARDCODED_TENANT =
  process.env.NEXT_PUBLIC_HARDCODED_TENANT || (DISABLE_AUTHENTICATION ? 'workflowai' : undefined);

export const STRIPE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;

export const TASK_RUN_ID_PARAM = 'runId';

export const UNKNOWN_USER_ID_COOKIE_NAME = 'x-unknown-user-id';
