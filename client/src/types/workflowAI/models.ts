export type AIReviewer = {
  reviewer_type?: 'ai';
};

export type APIKeyResponse = {
  id: string;
  name: string;
  partial_key: string;
  created_at: string;
  last_used_at: string | null;
  created_by: core__domain__users__UserIdentifier;
};

export type APIKeyResponseCreated = {
  id: string;
  name: string;
  partial_key: string;
  created_at: string;
  last_used_at: string | null;
  created_by: core__domain__users__UserIdentifier;
  key: string;
};

export type APIToolCallRequest = {
  /**
   * The id of the tool use. The id should be used when returning the result.
   */
  id: string;
  /**
   * The name of the tool
   */
  name: string;
  /**
   * The input tool should be executed with
   */
  input: Record<string, unknown>;
};

export type AgentSchema = {
  /**
   * The name of the task in Title Case
   */
  task_name: string;
  /**
   * The JSON schema of the task input
   */
  input_json_schema?: Record<string, unknown> | null;
  /**
   * The JSON schema of the agent output
   */
  output_json_schema?: Record<string, unknown> | null;
};

export type AmazonBedrockConfig = {
  provider?: 'amazon_bedrock';
  aws_bedrock_access_key: string;
  aws_bedrock_secret_key: string;
  resource_id_x_model_map: Record<string, string>;
  available_model_x_region_map: Record<string, string>;
  default_region?: string;
};

export type AnnotateFeedbackRequest = {
  annotation: 'resolved' | 'incorrect' | 'correct';
  comment?: string | null;
};

export type AnthropicConfig = {
  provider?: 'anthropic';
  api_key: string;
  url?: string;
};

export type AudioContentDict = {
  type: 'audio_url';
  audio_url: AudioURLDict;
};

export type AudioURLDict = {
  url: string;
};

export type AutomaticPaymentRequest = {
  opt_in: boolean;
  threshold?: number | null;
  balance_to_maintain?: number | null;
};

export type AzureOpenAIConfig = {
  provider?: 'azure_openai';
  deployments: Record<string, Record<string, string | Array<string>>>;
  api_version?: string;
  default_region?: string;
};

export type BaseFeature = {
  /**
   * The name of the feature, displayed in the UI
   */
  name: string;
  /**
   * A description of the feature, displayed in the UI
   */
  description: string;
  /**
   * The specifications of the feature, used to generate the feature input and output schema, for internal use only, NOT displayed in the UI. To be provided for 'static' feature suggestions only, null otherwise
   */
  specifications: string | null;
};

export type Body_upload_file__tenant__upload__task_id__post = {
  file: Blob | File;
};

export type BuildAgentIteration = {
  user_message: string;
  assistant_answer: string;
  /**
   * The task schema of the task generated in this iteration
   */
  task_schema?: AgentSchema | null;
};

export type BuildAgentRequest = {
  /**
   * The previous iteration of the task building process, as returned by the API
   */
  previous_iterations?: Array<BuildAgentIteration> | null;
  user_message: string;
  /**
   * Whether to stream the task building process
   */
  stream?: boolean;
};

export type CacheUsage = 'auto' | 'always' | 'never' | 'when_available' | 'only';

export type ChatMessage = {
  /**
   * The role of the message sender
   */
  role: 'USER' | 'ASSISTANT';
  /**
   * The content of the message
   */
  content: string;
};

export type CheckInstructionsRequest = {
  instructions: string;
};

export type CheckInstructionsResponse = {
  is_template: boolean;
  is_valid: boolean;
  error?: api__routers__task_schemas_v1__CheckInstructionsResponse__Error | null;
};

export type CodeBlock = {
  imports: string;
  code: string;
};

export type CreateAPIKeyRequest = {
  name: string;
};

export type CreateAgentRequest = {
  /**
   * The agent id, must be unique per tenant and URL safe
   */
  id?: string;
  /**
   * The input schema for the agent
   */
  input_schema: Record<string, unknown>;
  /**
   * The output schema for the agent
   */
  output_schema: Record<string, unknown>;
  /**
   * The name of the agent, if not provided, a TitleCase version of the id is used
   */
  name?: string;
  /**
   * the chat messages that originated the creation of the task, if created from the chat UI
   */
  chat_messages?: Array<ChatMessage> | null;
  /**
   * By default, the schemas are sanitized to make sure that slight changes in schema do not result
   * in a new agent schema id being generated. The schema that we store is then a schema compatible with the
   * original one for validation purposes.
   * The sanitation includes:
   * - splatting $refs that are not specific to WorkflowAI
   * - replacing nullable optional fields with simply optional fields
   * - ordering the `required` field
   * - removing anyOf, oneOf and allOf when possible
   * - adding missing type keys
   *
   */
  sanitize_schemas?: boolean;
};

export type CreateAgentResponse = {
  /**
   * A human readable, url safe id for the agent
   */
  id: string;
  /**
   * A unique integer identifier for the agent
   */
  uid: number;
  /**
   * The name of the agent
   */
  name: string;
  /**
   * The id of the created schema
   */
  schema_id: number;
  /**
   * The id of the created variant
   */
  variant_id: string;
};

export type CreateFeedbackRequest = {
  /**
   * The feedback token, as returned in the run payload
   */
  feedback_token: string;
  outcome: 'positive' | 'negative';
  /**
   * An optional comment for the feedback
   */
  comment?: string | null;
  /**
   * An ID for the user that is posting the feedback. Only a single feedback per user (including anonymous) per feedback_token is allowed. Posting a new feedback will overwrite the existing one.
   */
  user_id?: string | null;
};

export type CreateFeedbackResponse = {
  id: string;
  outcome: 'positive' | 'negative';
  comment: string | null;
  user_id: string | null;
};

export type CreatePaymentIntentRequest = {
  amount: number;
};

export type CreateReviewRequest = {
  outcome: 'positive' | 'negative';
  comment?: string | null;
};

export type CreateTaskGroupRequest = {
  /**
   * The id of the group. If not provided a uuid will be generated.
   */
  id?: string | null;
  /**
   * The properties used for executing runs.
   */
  properties: TaskGroupProperties_Input;
  /**
   * A list of tags associated with the group. If not provided, tags are computed from the properties by creating strings from each key value pair <key>=<value>.
   */
  tags?: Array<string> | null;
  /**
   * Set to true to store the group as is, without any runner validation.
   * Note that it means that the group will not be usable as is by internal runners.
   */
  use_external_runner?: boolean;
};

export type CreateTaskRunRequest = {
  /**
   * the input of the task. Must match the input schema
   */
  task_input: Record<string, unknown>;
  /**
   * the output of the task. Must match the output schema
   */
  task_output: Record<string, unknown>;
  /**
   * A reference to the task group the task run belongs to. By default, we consider that the group is external
   */
  group: DeprecatedVersionReference;
  /**
   * The id to use for a task run. If not provided a uuid will be generated
   */
  id?: string | null;
  /**
   * the time the run was started.
   */
  start_time?: string | null;
  /**
   * the time the run ended.
   */
  end_time?: string | null;
  /**
   * A list of labels for the task run. Labels are indexed and searchable
   */
  labels?: Array<string> | null;
  /**
   * Additional metadata to store with the task run.
   */
  metadata?: Record<string, unknown> | null;
  /**
   * The raw completions used to generate the task output.
   */
  llm_completions?: Array<LLMCompletion> | null;
  /**
   * The cost of the task run in USD
   */
  cost_usd?: number | null;
};

export type CreateVersionRequest = {
  properties: TaskGroupProperties_Input;
  /**
   * Whether to save the version after creating it. If false, the version will not be returned in the list of versions until it is saved. If save is not provided, the version is automatically saved if it is the first version for the schema.
   */
  save?: boolean | null;
};

export type CreateVersionResponse = {
  id: string;
  /**
   * @deprecated
   */
  iteration: number;
  semver: unknown[] | null;
  properties: TaskGroupProperties_Output;
};

export type CustomToolCreationChatMessage = {
  /**
   * The role of the message sender
   */
  role?: 'USER' | 'ASSISTANT' | null;
  /**
   * The content of the message
   */
  content?: string | null;
  /**
   * The proposed tool to create
   */
  tool?: Tool | null;
};

export type CustomerCreatedResponse = {
  customer_id: string;
};

export type DeployVersionRequest = {
  environment: VersionEnvironment;
};

export type DeployVersionResponse = {
  task_schema_id: number;
  version_id: string;
  environment: VersionEnvironment;
  deployed_at: string;
};

export type DeployedVersionsResponse = {
  /**
   * The group id either client provided or generated, stable for given set of properties
   */
  id?: string;
  /**
   * The semantic version of the task group
   */
  semver?: MajorMinor | null;
  /**
   * The schema id of the task group, incremented for each new schema
   */
  schema_id?: number;
  /**
   * The iteration of the group, incremented for each new group
   */
  iteration?: number;
  /**
   * The number of runs in the group
   */
  run_count?: number;
  /**
   * The properties used for executing the run.
   */
  properties: TaskGroupProperties_Output;
  /**
   * A list of tags associated with the group. When empty, tags are computed from the properties.
   */
  tags: Array<string>;
  /**
   * A list of aliases to use in place of iteration or id. An alias can be used to uniquely identify a group for a given task.
   */
  aliases?: Array<string> | null;
  /**
   * Whether the group is external, i-e not creating by internal runners
   */
  is_external?: boolean | null;
  /**
   * Indicates if the task group is marked as favorite
   */
  is_favorite?: boolean | null;
  /**
   * Additional notes or comments about the task group
   */
  notes?: string | null;
  /**
   * A hash computed based on task group properties, used for similarity comparisons
   */
  similarity_hash?: string;
  benchmark_for_datasets?: Array<string> | null;
  /**
   * The user who favorited the task group
   */
  favorited_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who created the task group
   */
  created_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who deployed the task group
   */
  deployed_by?: core__domain__users__UserIdentifier | null;
  /**
   * The last time the task group was active
   */
  last_active_at?: string | null;
  /**
   * The time the task group was created
   */
  created_at?: string | null;
  recent_runs_count?: number;
  deployments?: Array<Deployment> | null;
};

export type Deployment = {
  environment: VersionEnvironment;
  deployed_at: string;
  deployed_by?: core__domain__users__UserIdentifier | null;
};

/**
 * Refer to an existing group or create a new one with the given properties.
 * Only one of id, iteration or properties must be provided
 */
export type DeprecatedVersionReference = {
  /**
   * The id of an existing group
   */
  id?: string | null;
  /**
   * An iteration for an existing group.
   */
  iteration?: number | null;
  /**
   * The properties to evaluate the task schema with. A group will be created if needed
   */
  properties?: TaskGroupProperties_Input | null;
  /**
   * An alias for the group
   */
  alias?: string | null;
  /**
   * Whether the group is external, i-e not created by internal runners
   */
  is_external?: boolean | null;
};

export type DocumentContentDict = {
  type: 'document_url';
  source: DocumentURLDict;
};

export type DocumentURLDict = {
  url: string;
};

export type EditSchemaToolCall = {
  tool_name?: string;
  status?: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed';
  /**
   * Whether the tool call should be automatically executed by on the frontend (true), or if the user should be prompted to run the tool call (false).
   */
  auto_run?: boolean | null;
  tool_call_id?: string;
  /**
   * The message to edit the agent schema with.
   */
  edition_request_message?: string | null;
};

export type FeaturePreviewRequest = {
  feature: BaseFeature;
  /**
   * To provide for company-specific feature suggestions, null otherwise
   */
  company_context: string | null;
};

export type FeatureSchemas = {
  input_schema?: Record<string, unknown> | null;
  output_schema?: Record<string, unknown> | null;
};

export type FeatureSectionPreview = {
  name: string;
  tags: Array<TagPreview>;
};

export type FeatureSectionResponse = {
  sections?: Array<FeatureSectionPreview> | null;
};

export type Feedback = {
  outcome: 'positive' | 'negative';
  annotation: 'resolved' | 'incorrect' | 'correct' | null;
};

export type FeedbackItem = {
  id: string;
  outcome: 'positive' | 'negative';
  user_id?: string | null;
  comment?: string | null;
  created_at: string;
  annotation: 'resolved' | 'incorrect' | 'correct' | null;
  run_id: string;
};

export type FewShotConfiguration = {
  /**
   * The number of few-shot examples to use for the task
   */
  count?: number | null;
  /**
   * The selection method to use for few-shot examples
   */
  selection?: 'latest' | 'manual' | string | null;
  /**
   * The few-shot examples used for the task. If provided, count and selection are ignored. If not provided, count and selection are used to select examples and the examples list will be set in the final group.
   */
  examples?: Array<FewShotExample> | null;
};

export type FewShotExample = {
  task_input: Record<string, unknown>;
  task_output: Record<string, unknown>;
};

export type FieldQuery = {
  field_name: string;
  operator: SearchOperator;
  values: Array<unknown>;
  type?: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array' | 'null' | 'array_length' | 'date' | null;
};

export type File = {
  content_type?: string | null;
  base64_data: string;
};

export type FileInputRequest = {
  file_id: string;
  data: string;
  format: 'm4a' | 'mp3' | 'webm' | 'mp4' | 'mpga' | 'wav' | 'mpeg';
};

export type FullVersionProperties = {
  /**
   * The LLM model used for the run
   */
  model?: string | null;
  /**
   * The LLM provider used for the run
   */
  provider?: string | null;
  /**
   * The temperature for generation
   */
  temperature?: number | null;
  /**
   * The instructions passed to the runner in order to generate the prompt.
   */
  instructions?: string | null;
  /**
   * The maximum tokens to generate in the prompt
   */
  max_tokens?: number | null;
  /**
   * The name of the runner used
   */
  runner_name?: string | null;
  /**
   * The version of the runner used
   */
  runner_version?: string | null;
  /**
   * Few shot configuration
   */
  few_shot?: FewShotConfiguration | null;
  /**
   * The template name used for the task
   */
  template_name?: string | null;
  /**
   * Whether to use chain of thought prompting for the task
   */
  is_chain_of_thought_enabled?: boolean | null;
  enabled_tools?: Array<ToolKind | Tool_Output> | null;
  /**
   * Whether to use structured generation for the task
   */
  is_structured_generation_enabled?: boolean | null;
  has_templated_instructions?: boolean | null;
  /**
   * The name of the model
   */
  model_name?: string | null;
  /**
   * The icon of the model
   */
  model_icon?: string | null;
  [key: string]: unknown;
};

export type GenerateAgentInputToolCall = {
  tool_name?: string;
  status?: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed';
  /**
   * Whether the tool call should be automatically executed by on the frontend (true), or if the user should be prompted to run the tool call (false).
   */
  auto_run?: boolean | null;
  tool_call_id?: string;
  /**
   * The instructions on how to generate the agent input, this message will be passed to the input generation agent.
   */
  instructions?: string | null;
};

export type GenerateCodeBlockRequest = {
  group_iteration: number;
  group_environment: string;
  example_task_run_input: Record<string, unknown>;
  url?: string | null;
  secondary_input?: Record<string, unknown> | null;
  separate_run_and_stream?: boolean;
};

export type GenerateCodeBlockResponse = {
  sdk: Snippet;
  run: Snippet | RunSnippet;
};

export type GenerateInputRequest = {
  instructions?: string;
  /**
   * The base input to migrate to the new schema
   */
  base_input?: Record<string, unknown> | null;
  stream?: boolean;
};

export type GenerateTaskPreviewRequest = {
  /**
   * the chat messages that originated the creation of the task to generate a preview for
   */
  chat_messages: Array<ChatMessage>;
  /**
   * the input schema of the task to generate a preview for
   */
  task_input_schema: Record<string, unknown>;
  /**
   * the output schema of the task to generate a preview for
   */
  task_output_schema: Record<string, unknown>;
  /**
   * The current task preview (input, output) to reuse and update, if already existing
   */
  current_preview?: TaskPreview | null;
};

export type GetFeedbackResponse = {
  outcome: 'positive' | 'negative' | null;
};

export type GoogleGeminiAPIProviderConfig = {
  provider?: 'google_gemini';
  api_key: string;
  url: string;
  default_block_threshold?: 'BLOCK_LOW_AND_ABOVE' | 'BLOCK_MEDIUM_AND_ABOVE' | 'BLOCK_ONLY_HIGH' | 'BLOCK_NONE' | null;
};

export type GoogleProviderConfig = {
  provider?: 'google';
  vertex_project: string;
  vertex_credentials: string;
  vertex_location: Array<string>;
  default_block_threshold?: 'BLOCK_LOW_AND_ABOVE' | 'BLOCK_MEDIUM_AND_ABOVE' | 'BLOCK_ONLY_HIGH' | 'BLOCK_NONE' | null;
};

export type GroqConfig = {
  provider?: 'groq';
  api_key: string;
};

export type HTTPValidationError = {
  detail?: Array<ValidationError>;
};

export type ImageContentDict = {
  type: 'image_url';
  image_url: ImageURLDict;
};

export type ImageURLDict = {
  url: string;
};

export type ImportInputsRequest = {
  /**
   * The text to import as input
   */
  inputs_text?: string | null;
  /**
   * An optional file to import as input.
   */
  inputs_file?: File | null;
  stream?: boolean;
};

export type ImprovePromptToolCall = {
  tool_name?: string;
  status?: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed';
  /**
   * Whether the tool call should be automatically executed by on the frontend (true), or if the user should be prompted to run the tool call (false).
   */
  auto_run?: boolean | null;
  tool_call_id?: string;
  /**
   * The id of the run to improve
   */
  run_id?: string | null;
  /**
   * The feedback on the run (what is wrong with the output of the run, what is the expected output, etc.).
   */
  run_feedback_message: string;
};

export type ImproveVersionRequest = {
  run_id?: string | null;
  variant_id?: string | null;
  instructions?: string | null;
  /**
   * A comment on why the task run was not optimal
   */
  user_evaluation: string;
  stream?: boolean;
};

export type InputEvaluationData = {
  task_input_hash: string;
  task_input: Record<string, unknown>;
  correct_outputs: Array<Record<string, unknown>>;
  incorrect_outputs: Array<Record<string, unknown>>;
  evaluation_instructions: string;
};

export type InputEvaluationPatchRequest = {
  /**
   * The evaluation instructions to use for the input
   */
  update_input_evaluation_instructions?: string | null;
  /**
   * A correct output to use in evaluations. If the output already existed as an incorrect output, the matching incorrect output is removed. If the output already existed in the correct outputs, the output is ignored
   */
  add_correct_output?: Record<string, unknown> | null;
  /**
   * A correct output to remove from evaluations
   */
  remove_correct_output?: Record<string, unknown> | null;
  /**
   * An incorrect output to use in evaluations. If the output already existed as a correct output, the matching correct output is removed. If the output already existed in the incorrect outputs, the output is ignored
   */
  add_incorrect_output?: Record<string, unknown> | null;
  /**
   * An incorrect output to remove from evaluations
   */
  remove_incorrect_output?: Record<string, unknown> | null;
};

export type InternalReasoningStep = {
  /**
   * A brief title for this step (maximum a few words)
   */
  title?: string | null;
  /**
   * The explanation for this step of reasoning
   */
  explaination?: string | null;
  /**
   * The output or conclusion from this step
   */
  output?: string | null;
};

export type Item = {
  field_name: string;
  /**
   * The operators that can be used with the field
   */
  operators: Array<string>;
  /**
   * The suggestions for the field
   */
  suggestions?: Array<unknown> | null;
  /**
   * The type of the field
   */
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array' | 'null' | 'array_length' | 'date';
};

export type LLMCompletion = {
  duration_seconds?: number | null;
  messages: Array<Record<string, unknown>>;
  response?: string | null;
  tool_calls?: Array<ToolCallRequestWithID> | null;
  usage: LLMUsage;
  provider: Provider;
};

export type LLMCompletionTypedMessages = {
  messages: Array<StandardMessage>;
  response?: string | null;
  usage: LLMUsage;
  duration_seconds?: number | null;
};

export type LLMCompletionsResponse = {
  completions: Array<LLMCompletionTypedMessages>;
};

export type LLMUsage = {
  completion_token_count?: number | null;
  completion_cost_usd?: number | null;
  reasoning_token_count?: number | null;
  prompt_token_count?: number | null;
  /**
   * The part of the prompt_token_count that were cached from a previous request.
   */
  prompt_token_count_cached?: number | null;
  prompt_cost_usd?: number | null;
  prompt_audio_token_count?: number | null;
  prompt_audio_duration_seconds?: number | null;
  prompt_image_count?: number | null;
  model_context_window_size?: number | null;
};

export type ListModelsRequest = {
  /**
   * The instructions to use to build the models list, because instructions contains tools, and not all models support all tools.
   */
  instructions?: string | null;
  /**
   * Wether the agent is using tools. This flag is mainly fed by the SDK when external tools are used.
   */
  requires_tools?: boolean;
};

export type MajorMinor = unknown[];

export type MajorVersion = {
  major: number;
  schema_id: number;
  minors: Array<MinorVersion>;
  /**
   * The user who created the version
   */
  created_by?: api__schemas__user_identifier__UserIdentifier | null;
  created_at: string;
  properties: MajorVersionProperties;
  previous_version: PreviousVersion | null;
};

export type MajorVersionProperties = {
  temperature: number;
  instructions: string;
  /**
   * The id of the full schema, including versions and examples
   */
  task_variant_id: string | null;
};

export type MetaAgentChatMessage = {
  /**
   * The role of the message sender, 'USER' is the actual human user browsing the playground, 'PLAYGROUND' are automated messages sent by the playground to the agent, and 'ASSISTANT' being the assistant generated by the agent
   */
  role: 'USER' | 'PLAYGROUND' | 'ASSISTANT';
  /**
   * The content of the message
   */
  content: string;
  /**
   * The tool call to run in the frontend to help the user improve its agent instructions.
   */
  tool_call?:
    | ImprovePromptToolCall
    | EditSchemaToolCall
    | RunCurrentAgentOnModelsToolCall
    | GenerateAgentInputToolCall
    | null;

  feedback_token?: string | null;
};

export type MetaAgentChatRequest = {
  schema_id: number;
  /**
   * The state of the playground
   */
  playground_state: PlaygroundState;
  /**
   * The list of messages in the conversation, the last message being the most recent one
   */
  messages: Array<MetaAgentChatMessage>;
};

export type MinorVersion = {
  /**
   * The id of the full version
   */
  id: string;
  /**
   * @deprecated
   */
  iteration: number;
  model: Model | string;
  deployments: Array<VersionDeploymentMetadata> | null;
  cost_estimate_usd: number | null;
  /**
   * The last time the task version minor was active
   */
  last_active_at: string | null;
  is_favorite: boolean | null;
  favorited_by: api__schemas__user_identifier__UserIdentifier | null;
  created_by: api__schemas__user_identifier__UserIdentifier | null;
  notes: string | null;
  run_count: number | null;
  minor: number;
  properties: ShortVersionProperties;
};

export type MistralAIConfig = {
  provider?: 'mistral_ai';
  url?: string;
  api_key: string;
};

export type Model =
  | 'gpt-4o-latest'
  | 'gemini-2.0-flash-latest'
  | 'claude-3-5-sonnet-latest'
  | 'gemini-1.5-flash-latest'
  | 'gpt-4o-2024-11-20'
  | 'gpt-4o-2024-08-06'
  | 'gpt-4o-2024-05-13'
  | 'gpt-4o-mini-latest'
  | 'gpt-4o-mini-2024-07-18'
  | 'o3-mini-latest-high'
  | 'o3-mini-latest-medium'
  | 'o3-mini-latest-low'
  | 'o3-mini-2025-01-31-high'
  | 'o3-mini-2025-01-31-medium'
  | 'o3-mini-2025-01-31-low'
  | 'o1-2024-12-17-high'
  | 'o1-2024-12-17'
  | 'o1-2024-12-17-low'
  | 'o1-preview-2024-09-12'
  | 'o1-mini-latest'
  | 'o1-mini-2024-09-12'
  | 'gpt-4.5-preview-2025-02-27'
  | 'gpt-4o-audio-preview-2024-12-17'
  | 'gpt-4o-audio-preview-2024-10-01'
  | 'gpt-4-turbo-2024-04-09'
  | 'gpt-4-0125-preview'
  | 'gpt-4-1106-preview'
  | 'gpt-4-1106-vision-preview'
  | 'gpt-3.5-turbo-0125'
  | 'gpt-3.5-turbo-1106'
  | 'gemini-2.0-flash-001'
  | 'gemini-2.0-flash-lite-001'
  | 'gemini-2.0-flash-lite-preview-02-05'
  | 'gemini-2.0-pro-exp-02-05'
  | 'gemini-2.0-flash-exp'
  | 'gemini-2.0-flash-thinking-exp-1219'
  | 'gemini-2.0-flash-thinking-exp-01-21'
  | 'gemini-1.5-pro-latest'
  | 'gemini-1.5-pro-002'
  | 'gemini-1.5-pro-001'
  | 'gemini-1.5-pro-preview-0514'
  | 'gemini-1.5-pro-preview-0409'
  | 'gemini-1.5-flash-002'
  | 'gemini-1.5-flash-001'
  | 'gemini-1.5-flash-8b'
  | 'gemini-1.5-flash-preview-0514'
  | 'gemini-exp-1206'
  | 'gemini-exp-1121'
  | 'gemini-1.0-pro-002'
  | 'gemini-1.0-pro-001'
  | 'gemini-1.0-pro-vision-001'
  | 'claude-3-7-sonnet-latest'
  | 'claude-3-7-sonnet-20250219'
  | 'claude-3-5-sonnet-20241022'
  | 'claude-3-5-sonnet-20240620'
  | 'claude-3-5-haiku-latest'
  | 'claude-3-5-haiku-20241022'
  | 'claude-3-opus-20240229'
  | 'claude-3-sonnet-20240229'
  | 'claude-3-haiku-20240307'
  | 'llama-3.3-70b'
  | 'llama-3.2-90b'
  | 'llama-3.2-11b'
  | 'llama-3.2-11b-vision'
  | 'llama-3.2-3b'
  | 'llama-3.2-1b'
  | 'llama-3.2-90b-vision-preview'
  | 'llama-3.2-90b-text-preview'
  | 'llama-3.2-11b-text-preview'
  | 'llama-3.2-3b-preview'
  | 'llama-3.2-1b-preview'
  | 'llama-3.1-405b'
  | 'llama-3.1-70b'
  | 'llama-3.1-8b'
  | 'llama3-70b-8192'
  | 'llama3-8b-8192'
  | 'mixtral-8x7b-32768'
  | 'mistral-large-2-latest'
  | 'mistral-large-2-2407'
  | 'mistral-large-latest'
  | 'mistral-large-2411'
  | 'pixtral-large-latest'
  | 'pixtral-large-2411'
  | 'pixtral-12b-2409'
  | 'ministral-3b-2410'
  | 'ministral-8b-2410'
  | 'mistral-small-2409'
  | 'codestral-mamba-2407'
  | 'qwen-v3p2-32b-instruct'
  | 'deepseek-v3-2412'
  | 'deepseek-r1-2501';

export type ModelMetadata = {
  /**
   * The name of the provider for the model
   */
  provider_name: string;
  /**
   * The price per input token in USD
   */
  price_per_input_token_usd: number;
  /**
   * The price per output token in USD
   */
  price_per_output_token_usd: number;
  /**
   * The date the model was released
   */
  release_date: string;
  /**
   * The context window of the model in tokens
   */
  context_window_tokens: number;
  /**
   * The quality index of the model, from 0 to 100. None if not available. Source: artificialanalysis.ai
   */
  quality_index: number;
};

export type ModelResponse = {
  id: string;
  name: string;
  /**
   * The url of the icon to display for the model
   */
  icon_url: string;
  /**
   * The modes supported by the model
   */
  modes: Array<string>;
  /**
   * Why the model does not support the current schema. Only provided if the model is not supported by the current schema.
   */
  is_not_supported_reason: string | null;
  /**
   * The average cost per run in USD
   */
  average_cost_per_run_usd: number | null;
  /**
   * Whether the model is the latest in its family. In other wordsby default, only models with is_latest=True should be displayed.
   */
  is_latest: boolean;
  /**
   * The metadata of the model
   */
  metadata: ModelMetadata;
  /**
   * If true, the model will be used as default model.
   */
  is_default?: boolean;
  /**
   * The providers that support this model
   */
  providers: Array<Provider>;
};

export type OpenAIConfig = {
  provider?: 'openai';
  url?: string;
  api_key: string;
};

export type Page_DeployedVersionsResponse_ = {
  items: Array<DeployedVersionsResponse>;
  count?: number | null;
};

export type Page_FeedbackItem_ = {
  items: Array<FeedbackItem>;
  count?: number | null;
};

export type Page_InputEvaluationData_ = {
  items: Array<InputEvaluationData>;
  count?: number | null;
};

export type Page_MajorVersion_ = {
  items: Array<MajorVersion>;
  count?: number | null;
};

export type Page_ModelResponse_ = {
  items: Array<ModelResponse>;
  count?: number | null;
};

export type Page_Review_ = {
  items: Array<Review>;
  count?: number | null;
};

export type Page_RunItemV1_ = {
  items: Array<RunItemV1>;
  count?: number | null;
};

export type Page_SerializableTaskRun_ = {
  items: Array<SerializableTaskRun>;
  count?: number | null;
};

export type Page_SerializableTask_ = {
  items: Array<SerializableTask>;
  count?: number | null;
};

export type Page_TaskGroupWithCost_ = {
  items: Array<TaskGroupWithCost>;
  count?: number | null;
};

export type Page_VersionsResponse_ = {
  items: Array<VersionsResponse>;
  count?: number | null;
};

export type PartialTaskVersion = {
  schema_id: number;
  variant_id: string;
  description?: string | null;
  input_schema_version: string;
  output_schema_version: string;
  created_at?: string;
  is_hidden?: boolean | null;
  last_active_at?: string | null;
};

export type PatchReviewBenchmarkRequest = {
  add_versions?: Array<number> | null;
  remove_versions?: Array<number> | null;
};

export type PaymentIntentCreatedResponse = {
  client_secret: string;
  payment_intent_id: string;
};

export type PaymentMethodIdResponse = {
  payment_method_id: string;
};

export type PaymentMethodRequest = {
  payment_method_id: string;
  payment_method_currency?: string;
};

export type PaymentMethodResponse = {
  payment_method_id: string;
  last4: string;
  brand: string;
  exp_month: number;
  exp_year: number;
};

export type PlaygroundState = {
  /**
   * The input for the agent
   */
  agent_input?: Record<string, unknown> | null;
  /**
   * The instructions for the agent
   */
  agent_instructions?: string | null;
  /**
   * The temperature for the agent
   */
  agent_temperature?: number | null;
  /**
   * The models currently selected in the playground
   */
  selected_models: SelectedModels;
  /**
   * The ids of the runs currently displayed in the playground
   */
  agent_run_ids: Array<string>;
};

export type PreviousVersion = {
  major: number;
  changelog: Array<string>;
};

export type Provider =
  | 'fireworks'
  | 'amazon_bedrock'
  | 'openai'
  | 'azure_openai'
  | 'google'
  | 'anthropic'
  | 'groq'
  | 'mistral_ai'
  | 'google_gemini';

export type ProviderSettings = {
  id: string;
  created_at: string;
  provider: Provider;
};

export type ReasoningStep = {
  title: string | null;
  step: string | null;
};

export type RespondToReviewRequest = {
  comment: string;
};

export type Review = {
  id: string;
  created_at: string;
  created_by: UserReviewer | AIReviewer;
  outcome: 'positive' | 'negative' | 'unsure' | null;
  status: 'in_progress' | 'completed';
  /**
   * A comment left by the reviewer
   * @deprecated
   */
  comment?: string | null;
  summary?: string | null;
  positive_aspects?: Array<string> | null;
  negative_aspects?: Array<string> | null;
};

export type ReviewBenchmark = {
  results: Array<VersionResult>;
  /**
   * Whether a new AI reviewer is being built.When done building, some reviews that need to be recomputed
   */
  is_building_ai_reviewer?: boolean;
};

export type RunConfig = {
  /**
   * The column to run the agent on the agent will be run on all columns
   */
  run_on_column?: 'column_1' | 'column_2' | 'column_3' | null;
  /**
   * The model to run the agent on the agent will be run on all models
   */
  model?: string | null;
};

export type RunCurrentAgentOnModelsToolCall = {
  tool_name?: string;
  status?: 'assistant_proposed' | 'user_ignored' | 'completed' | 'failed';
  /**
   * Whether the tool call should be automatically executed by on the frontend (true), or if the user should be prompted to run the tool call (false).
   */
  auto_run?: boolean | null;
  tool_call_id?: string;
  /**
   * The list of configurations to run the current agent on.
   */
  run_configs?: Array<RunConfig> | null;
};

export type RunItemV1 = {
  /**
   * the id of the task run
   */
  id: string;
  /**
   * the id of the task
   */
  task_id: string;
  /**
   * The id of the task run's schema
   */
  task_schema_id: number;
  version: Version;
  status: 'success' | 'failure';
  duration_seconds: number | null;
  cost_usd: number | null;
  /**
   * The time the task run was created
   */
  created_at: string;
  user_review: 'positive' | 'negative' | null;
  ai_review: 'positive' | 'negative' | 'unsure' | 'in_progress' | null;
  feedback?: Array<Feedback> | null;
  /**
   * A signed token that can be used to post feedback from a client side application
   */
  feedback_token: string;
  /**
   * A preview of the input data
   */
  task_input_preview: string;
  /**
   * A preview of the output data
   */
  task_output_preview: string;
  error: api__routers__runs_v1__RunItemV1__Error | null;
};

export type RunReplyRequest = {
  /**
   * The version of the task to reply to. If not provided the latest version is used.
   */
  version?: number | VersionEnvironment | TaskGroupProperties_Input | string | MajorMinor | null;
  user_message?: string | null;
  tool_results?: Array<ToolCallResult> | null;
  metadata?: Record<string, unknown> | null;
  stream?: boolean;
};

export type RunRequest = {
  task_input: Record<string, unknown>;
  version: number | VersionEnvironment | TaskGroupProperties_Input | string | MajorMinor;
  /**
   * An optional id, must be a valid uuid7. If not provided a uuid7 will be generated
   */
  id?: string;
  stream?: boolean;
  use_cache?: CacheUsage;
  /**
   * Additional metadata to store with the task run.
   */
  metadata?: Record<string, unknown> | null;
  /**
   * A list of labels for the task run. Labels are indexed and searchable
   * @deprecated
   */
  labels?: Array<string> | null;
  /**
   * Fields marked as private will not be saved, none by default.
   */
  private_fields?: Array<'task_input' | string> | null;
};

export type RunSnippet = {
  language?: 'python';
  common: string;
  run: CodeBlock;
  stream: CodeBlock;
};

export type RunV1 = {
  /**
   * the id of the task run
   */
  id: string;
  /**
   * the id of the task
   */
  task_id: string;
  /**
   * The id of the task run's schema
   */
  task_schema_id: number;
  version: Version;
  status: 'success' | 'failure';
  duration_seconds: number | null;
  cost_usd: number | null;
  /**
   * The time the task run was created
   */
  created_at: string;
  user_review: 'positive' | 'negative' | null;
  ai_review: 'positive' | 'negative' | 'unsure' | 'in_progress' | null;
  feedback?: Array<Feedback> | null;
  /**
   * A signed token that can be used to post feedback from a client side application
   */
  feedback_token: string;
  task_input: TaskInputDict;
  task_output: TaskOutputDict;
  reasoning_steps: Array<ReasoningStep> | null;
  error: api__routers__runs_v1__RunV1__Error | null;
  /**
   * Tool calls that should be executed client side.
   */
  tool_call_requests: Array<APIToolCallRequest> | null;
};

export type SearchFields = {
  /**
   * The fields that can be used in the search
   */
  fields: Array<Item>;
};

export type SearchOperator =
  | 'is'
  | 'is not'
  | 'is empty'
  | 'is not empty'
  | 'contains'
  | 'does not contain'
  | 'greater than'
  | 'greater than or equal to'
  | 'less than'
  | 'less than or equal to'
  | 'is between'
  | 'is not between'
  | 'is before'
  | 'is after';

export type SearchTaskRunsRequest = {
  /**
   * Optional list of field queries for searching task runs
   */
  field_queries?: Array<FieldQuery> | null;
  limit?: number;
  offset?: number;
};

export type SelectedModels = {
  /**
   * The id of the model selected in the first column of the playground, if empty, no model is selected in the first column
   */
  column_1: string | null;
  /**
   * The id of the model selected in the second column of the playground, if empty, no model is selected in the second column
   */
  column_2: string | null;
  /**
   * The id of the model selected in the third column of the playground, if empty, no model is selected in the third column
   */
  column_3: string | null;
};

export type SerializableTask = {
  id: string;
  name: string;
  description?: string | null;
  is_public?: boolean | null;
  tenant?: string;
  average_cost_usd?: number | null;
  run_count?: number | null;
  versions: Array<PartialTaskVersion>;
  uid: number;
};

export type SerializableTaskIO = {
  /**
   * the version of the schema definition. Titles and descriptions are ignored.
   */
  version: string;
  /**
   * A json schema
   */
  json_schema: Record<string, unknown>;
};

/**
 * A task run represents an instance of a task being executed
 */
export type SerializableTaskRun = {
  /**
   * the id of the task run. If not provided a uuid will be generated
   */
  id: string;
  /**
   * the uid of the task
   */
  task_uid?: number;
  /**
   * the id of the associated task, read only
   */
  task_id: string;
  /**
   * the schema idx of the associated task, read only
   */
  task_schema_id: number;
  /**
   * a hash describing the input
   */
  task_input_hash: string;
  /**
   * A preview of the input data. This is used to display the input data in the UI.
   */
  task_input_preview?: string;
  /**
   * a hash describing the output
   */
  task_output_hash: string;
  /**
   * A preview of the output data. This is used to display the output data in the UI.
   */
  task_output_preview?: string;
  group: TaskGroup;
  status?: 'success' | 'failure';
  error?: core__domain__error_response__ErrorResponse__Error | null;
  duration_seconds?: number | null;
  cost_usd?: number | null;
  /**
   * The time the task run was created
   */
  created_at?: string;
  /**
   * The time the task run was last updated
   */
  updated_at?: string;
  /**
   * The id of the example that share the same input as the task run
   */
  example_id?: string | null;
  user_review?: 'positive' | 'negative' | null;
  ai_review?: 'in_progress' | 'positive' | 'negative' | 'unsure' | null;
  author_tenant?: string | null;
  author_uid?: number | null;
  eval_hash?: string;
  task_input: TaskInputDict;
  task_output: TaskOutputDict;
  start_time?: string | null;
  end_time?: string | null;
  /**
   * The corrections that were applied to the task output if used as a base for an evaluation
   */
  corrections?: Record<string, unknown> | null;
  /**
   * A set of labels that are attached to the task runs. They are indexed.
   */
  labels?: Array<string> | null;
  /**
   * A user set metadata key / value. Keys are not searchable.
   */
  metadata?: Record<string, unknown> | null;
  /**
   * A list of raw completions used to generate the task output
   */
  llm_completions?: Array<LLMCompletion> | null;
  /**
   * The id of the config that was used to run the task
   */
  from_cache?: boolean | null;
  private_fields?: Array<string> | null;
  /**
   * Whether the task run is triggered using sdk/api
   */
  is_active?: boolean | null;
  reasoning_steps?: Array<InternalReasoningStep> | null;
  /**
   * A list of tool calls used to generate the task output
   */
  tool_calls?: Array<ToolCall> | null;
  tool_call_requests?: Array<ToolCallRequestWithID> | null;
  version_changed?: boolean | null;
  is_external?: boolean | null;
};

export type ShortVersionProperties = {
  /**
   * The LLM model used for the run
   */
  model?: string | null;
  /**
   * The name of the model
   */
  model_name?: string | null;
  /**
   * The icon of the model
   */
  model_icon?: string | null;
  /**
   * The LLM provider used for the run
   */
  provider?: string | null;
  /**
   * The temperature for generation
   */
  temperature?: number | null;
};

export type Snippet = {
  language: 'python' | 'bash';
  code: string;
};

export type StandardMessage = {
  role: 'system' | 'user' | 'assistant' | null;
  content:
    | string
    | Array<
        | TextContentDict
        | ImageContentDict
        | AudioContentDict
        | DocumentContentDict
        | ToolCallRequestDict
        | ToolCallResultDict
      >;
};

export type TagPreview = {
  name: string;
  kind: 'static' | 'company_specific';
};

export type TaskEvaluationPatchRequest = {
  evaluation_instructions: string;
};

export type TaskEvaluationResponse = {
  /**
   * The task level instructions for the AI reviewer. The instructions are passed with every evaluation.
   */
  evaluation_instructions: string;
};

export type TaskGroup = {
  /**
   * The group id either client provided or generated, stable for given set of properties
   */
  id?: string;
  /**
   * The semantic version of the task group
   */
  semver?: MajorMinor | null;
  /**
   * The schema id of the task group, incremented for each new schema
   */
  schema_id?: number;
  /**
   * The iteration of the group, incremented for each new group
   */
  iteration?: number;
  /**
   * The number of runs in the group
   */
  run_count?: number;
  /**
   * The properties used for executing the run.
   */
  properties: TaskGroupProperties_Output;
  /**
   * A list of tags associated with the group. When empty, tags are computed from the properties.
   */
  tags: Array<string>;
  /**
   * A list of aliases to use in place of iteration or id. An alias can be used to uniquely identify a group for a given task.
   */
  aliases?: Array<string> | null;
  /**
   * Whether the group is external, i-e not creating by internal runners
   */
  is_external?: boolean | null;
  /**
   * Indicates if the task group is marked as favorite
   */
  is_favorite?: boolean | null;
  /**
   * Additional notes or comments about the task group
   */
  notes?: string | null;
  /**
   * A hash computed based on task group properties, used for similarity comparisons
   */
  similarity_hash?: string;
  benchmark_for_datasets?: Array<string> | null;
  /**
   * The user who favorited the task group
   */
  favorited_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who created the task group
   */
  created_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who deployed the task group
   */
  deployed_by?: core__domain__users__UserIdentifier | null;
  /**
   * The last time the task group was active
   */
  last_active_at?: string | null;
  /**
   * The time the task group was created
   */
  created_at?: string | null;
};

/**
 * Properties that described a way a task run was executed.
 * Although some keys are provided as an example, any key:value are accepted
 */
export type TaskGroupProperties_Input = {
  /**
   * The LLM model used for the run
   */
  model?: string | null;
  /**
   * The LLM provider used for the run
   */
  provider?: string | null;
  /**
   * The temperature for generation
   */
  temperature?: number | null;
  /**
   * The instructions passed to the runner in order to generate the prompt.
   */
  instructions?: string | null;
  /**
   * The maximum tokens to generate in the prompt
   */
  max_tokens?: number | null;
  /**
   * The name of the runner used
   */
  runner_name?: string | null;
  /**
   * The version of the runner used
   */
  runner_version?: string | null;
  /**
   * Few shot configuration
   */
  few_shot?: FewShotConfiguration | null;
  /**
   * The template name used for the task
   */
  template_name?: string | null;
  /**
   * Whether to use chain of thought prompting for the task
   */
  is_chain_of_thought_enabled?: boolean | null;
  enabled_tools?: Array<ToolKind | core__domain__tool__Tool> | null;
  /**
   * Whether to use structured generation for the task
   */
  is_structured_generation_enabled?: boolean | null;
  has_templated_instructions?: boolean | null;
  [key: string]: unknown;
};

/**
 * Properties that described a way a task run was executed.
 * Although some keys are provided as an example, any key:value are accepted
 */
export type TaskGroupProperties_Output = {
  /**
   * The LLM model used for the run
   */
  model?: string | null;
  /**
   * The LLM provider used for the run
   */
  provider?: string | null;
  /**
   * The temperature for generation
   */
  temperature?: number | null;
  /**
   * The instructions passed to the runner in order to generate the prompt.
   */
  instructions?: string | null;
  /**
   * The maximum tokens to generate in the prompt
   */
  max_tokens?: number | null;
  /**
   * The name of the runner used
   */
  runner_name?: string | null;
  /**
   * The version of the runner used
   */
  runner_version?: string | null;
  /**
   * Few shot configuration
   */
  few_shot?: FewShotConfiguration | null;
  /**
   * The template name used for the task
   */
  template_name?: string | null;
  /**
   * Whether to use chain of thought prompting for the task
   */
  is_chain_of_thought_enabled?: boolean | null;
  enabled_tools?: Array<ToolKind | Tool_Output> | null;
  /**
   * Whether to use structured generation for the task
   */
  is_structured_generation_enabled?: boolean | null;
  has_templated_instructions?: boolean | null;
  [key: string]: unknown;
};

/**
 * Model representing an update to a task group.
 */
export type TaskGroupUpdate = {
  /**
   * A new alias for the group. If the alias is already used in another group of the task schema, it will be removed from the other group.
   * @deprecated
   */
  add_alias?: string | null;
  /**
   * An alias to remove from the group. The request is a noop if the group does not have the alias.
   * @deprecated
   */
  remove_alias?: string | null;
  /**
   * Set to True to mark the group as a favorite, False to unmark it, or None to leave it unchanged.
   */
  is_favorite?: boolean | null;
  /**
   * Additional notes or comments about the task group. Set to None to leave unchanged.
   */
  notes?: string | null;
  /**
   * The last time the task group was active.
   */
  last_active_at?: string | null;
};

export type TaskGroupWithCost = {
  /**
   * The group id either client provided or generated, stable for given set of properties
   */
  id?: string;
  /**
   * The semantic version of the task group
   */
  semver?: MajorMinor | null;
  /**
   * The schema id of the task group, incremented for each new schema
   */
  schema_id?: number;
  /**
   * The iteration of the group, incremented for each new group
   */
  iteration?: number;
  /**
   * The number of runs in the group
   */
  run_count?: number;
  /**
   * The properties used for executing the run.
   */
  properties: TaskGroupProperties_Output;
  /**
   * A list of tags associated with the group. When empty, tags are computed from the properties.
   */
  tags: Array<string>;
  /**
   * A list of aliases to use in place of iteration or id. An alias can be used to uniquely identify a group for a given task.
   */
  aliases?: Array<string> | null;
  /**
   * Whether the group is external, i-e not creating by internal runners
   */
  is_external?: boolean | null;
  /**
   * Indicates if the task group is marked as favorite
   */
  is_favorite?: boolean | null;
  /**
   * Additional notes or comments about the task group
   */
  notes?: string | null;
  /**
   * A hash computed based on task group properties, used for similarity comparisons
   */
  similarity_hash?: string;
  benchmark_for_datasets?: Array<string> | null;
  /**
   * The user who favorited the task group
   */
  favorited_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who created the task group
   */
  created_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who deployed the task group
   */
  deployed_by?: core__domain__users__UserIdentifier | null;
  /**
   * The last time the task group was active
   */
  last_active_at?: string | null;
  /**
   * The time the task group was created
   */
  created_at?: string | null;
  cost_estimate_usd?: number | null;
};

export type TaskInputDict = Record<string, unknown>;

export type TaskOutputDict = Record<string, unknown>;

export type TaskPreview = {
  /**
   * The preview input for the task
   */
  input: Record<string, unknown>;
  /**
   * The preview output for the task
   */
  output: Record<string, unknown>;
};

export type TaskSchemaResponse = {
  name: string;
  task_id: string;
  schema_id: number;
  input_schema: SerializableTaskIO;
  output_schema: SerializableTaskIO;
  is_hidden?: boolean | null;
  last_active_at?: string | null;
  latest_variant_id?: string | null;
};

export type TaskSchemaUpdateRequest = {
  is_hidden?: boolean | null;
};

export type TaskStats = {
  total_count: number;
  total_cost_usd: number;
  date: string;
};

export type TaskStatsResponse = {
  data: Array<TaskStats>;
};

export type TenantData = {
  uid?: number;
  tenant?: string;
  slug?: string;
  name?: string | null;
  org_id?: string | null;
  owner_id?: string | null;
  anonymous_user_id?: string | null;
  anonymous?: boolean | null;
  stripe_customer_id?: string | null;
  providers?: Array<ProviderSettings>;
  added_credits_usd?: number;
  current_credits_usd?: number;
  locked_for_payment?: boolean | null;
  last_payment_failed_at?: string | null;
  automatic_payment_enabled?: boolean;
  automatic_payment_threshold?: number | null;
  automatic_payment_balance_to_maintain?: number | null;
};

export type TextContentDict = {
  type: 'text';
  text: string;
};

export type Tool_Output = {
  /**
   * The name of the tool
   */
  name: string;
  /**
   * The description of the tool
   */
  description?: string;
  /**
   * The input class of the tool
   */
  input_schema: Record<string, unknown>;
  /**
   * The output class of the tool
   */
  output_schema: Record<string, unknown>;
};

export type ToolCall = {
  id: string;
  /**
   * The name of the tool that was executed
   */
  name: string;
  /**
   * A preview of the input to the tool
   */
  input_preview: string;
  /**
   * A preview of the output of the tool
   */
  output_preview: string | null;
  /**
   * The error that occurred during the tool call if any
   */
  error: string | null;
};

export type ToolCallRequestDict = {
  type: 'tool_call_request';
  id: string | null;
  tool_name: string;
  tool_input_dict: Record<string, unknown> | null;
};

export type ToolCallRequestWithID = {
  /**
   * The name of the tool called
   */
  tool_name: string;
  /**
   * The input of the tool call
   */
  tool_input_dict: Record<string, unknown>;
  /**
   * The id of the tool call
   */
  id?: string;
};

export type ToolCallResult = {
  id: string;
  output?: unknown | null;
  error?: string | null;
};

export type ToolCallResultDict = {
  type: 'tool_call_result';
  id: string | null;
  tool_name: string | null;
  tool_input_dict: Record<string, unknown> | null;
  result: unknown | null;
  error: string | null;
};

export type ToolCreationRequest = {
  /**
   * The list of previous messages in the conversation, the last message is the most recent one
   */
  messages: Array<CustomToolCreationChatMessage>;
};

export type ToolInputExampleRequest = {
  /**
   * The tool to generate an example input for
   */
  tool: api__routers__agents__new_tool_agent__ToolInputExampleRequest__Tool;
};

export type ToolKind =
  | '@search-google'
  | '@perplexity-sonar'
  | '@perplexity-sonar-reasoning'
  | '@perplexity-sonar-pro'
  | '@browser-text';

export type ToolOutputExampleRequest = {
  /**
   * The tool to generate an example output for
   */
  tool: api__routers__agents__new_tool_agent__ToolOutputExampleRequest__Tool;
  /**
   * The input of the tool to generate an example output for, if any
   */
  tool_input?: Record<string, unknown> | null;
};

export type UpdateTaskInstructionsRequest = {
  instructions: string;
  /**
   * The tools to include in the instructions. Any tool not listed here will be removed from the instructions.
   * If 'selected_tools' is None, no tools will be added or removed from the instructions.
   */
  selected_tools?: Array<ToolKind> | null;
};

export type UpdateTaskRequest = {
  /**
   * whether the task is public
   */
  is_public?: boolean | null;
  /**
   * the task display name
   */
  name?: string | null;
  /**
   * the task description
   */
  description?: string | null;
};

export type UpdateVersionNotesRequest = {
  notes: string;
};

export type UploadFileResponse = {
  url: string;
};

export type UserReviewer = {
  user_id?: string | null;
  /**
   * The user email
   */
  user_email?: string | null;
  reviewer_type?: 'user';
};

export type ValidationError = {
  loc: Array<string | number>;
  msg: string;
  type: string;
};

export type Version = {
  id: string;
  properties: TaskGroupProperties;
};

export type VersionDeploymentMetadata = {
  environment: VersionEnvironment;
  deployed_at: string;
  deployed_by: api__schemas__user_identifier__UserIdentifier | null;
};

export type VersionEnvironment = 'dev' | 'staging' | 'production';

export type VersionResult = {
  iteration: number;
  properties: ShortVersionProperties;
  /**
   * The number of positive reviews for the version
   */
  positive_review_count: number;
  /**
   * The number of positive reviews that were left by users
   */
  positive_user_review_count: number;
  /**
   * The number of negative reviews for the version,including both runs that were rejected and runs that failed because the output was invalid
   */
  negative_review_count: number;
  /**
   * The number of negative reviews that were left by users
   */
  negative_user_review_count: number;
  /**
   * The number of unsure reviews for the version
   */
  unsure_review_count: number;
  /**
   * The number of reviews that are still in progress for the version, either becausethe run has not yet completed or because the review has not yet been computed
   */
  in_progress_review_count: number;
  average_cost_usd: number | null;
  average_duration_seconds: number | null;
};

export type VersionV1 = {
  /**
   * The id of the full version
   */
  id: string;
  /**
   * @deprecated
   */
  iteration: number;
  model: Model | string;
  deployments: Array<VersionDeploymentMetadata> | null;
  cost_estimate_usd: number | null;
  /**
   * The last time the task version minor was active
   */
  last_active_at: string | null;
  is_favorite: boolean | null;
  favorited_by: api__schemas__user_identifier__UserIdentifier | null;
  created_by: api__schemas__user_identifier__UserIdentifier | null;
  notes: string | null;
  run_count: number | null;
  schema_id: number;
  semver: unknown[] | null;
  created_at: string;
  properties: FullVersionProperties;
  /**
   * The full input schema used for this version. Includes descriptions and examples
   */
  input_schema: Record<string, unknown>;
  /**
   * The full output schema used for this version. Includes descriptions and examples
   */
  output_schema: Record<string, unknown>;
};

export type VersionsResponse = {
  /**
   * The group id either client provided or generated, stable for given set of properties
   */
  id?: string;
  /**
   * The semantic version of the task group
   */
  semver?: MajorMinor | null;
  /**
   * The schema id of the task group, incremented for each new schema
   */
  schema_id?: number;
  /**
   * The iteration of the group, incremented for each new group
   */
  iteration?: number;
  /**
   * The number of runs in the group
   */
  run_count?: number;
  /**
   * The properties used for executing the run.
   */
  properties: TaskGroupProperties_Output;
  /**
   * A list of tags associated with the group. When empty, tags are computed from the properties.
   */
  tags: Array<string>;
  /**
   * A list of aliases to use in place of iteration or id. An alias can be used to uniquely identify a group for a given task.
   */
  aliases?: Array<string> | null;
  /**
   * Whether the group is external, i-e not creating by internal runners
   */
  is_external?: boolean | null;
  /**
   * Indicates if the task group is marked as favorite
   */
  is_favorite?: boolean | null;
  /**
   * Additional notes or comments about the task group
   */
  notes?: string | null;
  /**
   * A hash computed based on task group properties, used for similarity comparisons
   */
  similarity_hash?: string;
  benchmark_for_datasets?: Array<string> | null;
  /**
   * The user who favorited the task group
   */
  favorited_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who created the task group
   */
  created_by?: core__domain__users__UserIdentifier | null;
  /**
   * The user who deployed the task group
   */
  deployed_by?: core__domain__users__UserIdentifier | null;
  /**
   * The last time the task group was active
   */
  last_active_at?: string | null;
  /**
   * The time the task group was created
   */
  created_at?: string | null;
  recent_runs_count?: number;
};

export type api__routers__agents__new_tool_agent__ToolInputExampleRequest__Tool = {
  /**
   * The name of the tool to generate an example input for
   */
  name: string;
  /**
   * The description of the tool to generate an example input for
   */
  description: string;
  /**
   * The parameters of the tool in JSON Schema format
   */
  parameters: Record<string, unknown>;
};

export type api__routers__agents__new_tool_agent__ToolOutputExampleRequest__Tool = {
  /**
   * The name of the tool to generate an example output for
   */
  name: string;
  /**
   * The description of the tool to generate an example output for
   */
  description: string;
};

export type api__routers__runs_by_id__TranscriptionResponse = {
  transcriptions_by_keypath: Record<string, string>;
};

export type api__routers__runs_v1__RunItemV1__Error = {
  code:
    | 'max_tokens_exceeded'
    | 'failed_generation'
    | 'invalid_generation'
    | 'unknown_provider_error'
    | 'rate_limit'
    | 'server_overloaded'
    | 'invalid_provider_config'
    | 'provider_internal_error'
    | 'provider_unavailable'
    | 'read_timeout'
    | 'model_does_not_support_mode'
    | 'invalid_file'
    | 'max_tool_call_iteration'
    | 'structured_generation_error'
    | 'content_moderation'
    | 'task_banned'
    | 'timeout'
    | 'agent_run_failed'
    | 'bad_request'
    | 'missing_model'
    | 'object_not_found'
    | 'version_not_found'
    | 'agent_not_found'
    | 'agent_input_not_found'
    | 'agent_run_not_found'
    | 'example_not_found'
    | 'schema_not_found'
    | 'score_not_found'
    | 'evaluator_not_found'
    | 'organization_not_found'
    | 'config_not_found'
    | 'no_provider_supporting_model'
    | 'provider_does_not_support_model'
    | 'invalid_run_properties'
    | 'internal_error'
    | 'bad_request'
    | 'invalid_file'
    | 'entity_too_large'
    | 'unsupported_json_schema'
    | 'card_validation_error'
    | string;
  message: string;
};

export type api__routers__runs_v1__RunV1__Error = {
  code:
    | 'max_tokens_exceeded'
    | 'failed_generation'
    | 'invalid_generation'
    | 'unknown_provider_error'
    | 'rate_limit'
    | 'server_overloaded'
    | 'invalid_provider_config'
    | 'provider_internal_error'
    | 'provider_unavailable'
    | 'read_timeout'
    | 'model_does_not_support_mode'
    | 'invalid_file'
    | 'max_tool_call_iteration'
    | 'structured_generation_error'
    | 'content_moderation'
    | 'task_banned'
    | 'timeout'
    | 'agent_run_failed'
    | 'bad_request'
    | 'missing_model'
    | 'object_not_found'
    | 'version_not_found'
    | 'agent_not_found'
    | 'agent_input_not_found'
    | 'agent_run_not_found'
    | 'example_not_found'
    | 'schema_not_found'
    | 'score_not_found'
    | 'evaluator_not_found'
    | 'organization_not_found'
    | 'config_not_found'
    | 'no_provider_supporting_model'
    | 'provider_does_not_support_model'
    | 'invalid_run_properties'
    | 'internal_error'
    | 'bad_request'
    | 'invalid_file'
    | 'entity_too_large'
    | 'unsupported_json_schema'
    | 'card_validation_error'
    | string;
  message: string;
  details: Record<string, unknown> | null;
};

export type api__routers__task_schemas_v1__CheckInstructionsResponse__Error = {
  message: string;
  line_number: number | null;
  missing_keys?: Array<string> | null;
};

export type api__routers__transcriptions__TranscriptionResponse = {
  transcription: string;
};

export type api__schemas__user_identifier__UserIdentifier = {
  user_id?: string | null;
  user_email?: string | null;
};

export type core__domain__error_response__ErrorResponse__Error = {
  title?: string | null;
  details?: Record<string, unknown> | null;
  message?: string;
  status_code?: number;
  code?:
    | 'max_tokens_exceeded'
    | 'failed_generation'
    | 'invalid_generation'
    | 'unknown_provider_error'
    | 'rate_limit'
    | 'server_overloaded'
    | 'invalid_provider_config'
    | 'provider_internal_error'
    | 'provider_unavailable'
    | 'read_timeout'
    | 'model_does_not_support_mode'
    | 'invalid_file'
    | 'max_tool_call_iteration'
    | 'structured_generation_error'
    | 'content_moderation'
    | 'task_banned'
    | 'timeout'
    | 'agent_run_failed'
    | 'bad_request'
    | 'missing_model'
    | 'object_not_found'
    | 'version_not_found'
    | 'agent_not_found'
    | 'agent_input_not_found'
    | 'agent_run_not_found'
    | 'example_not_found'
    | 'schema_not_found'
    | 'score_not_found'
    | 'evaluator_not_found'
    | 'organization_not_found'
    | 'config_not_found'
    | 'no_provider_supporting_model'
    | 'provider_does_not_support_model'
    | 'invalid_run_properties'
    | 'internal_error'
    | 'bad_request'
    | 'invalid_file'
    | 'entity_too_large'
    | 'unsupported_json_schema'
    | 'card_validation_error'
    | string;
};

export type core__domain__fields__custom_tool_creation_chat_message__CustomToolCreationChatMessage__Tool = {
  /**
   * The name of the tool
   */
  name?: string | null;
  /**
   * The description of the tool
   */
  description?: string | null;
  /**
   * The parameters of the tool in JSON Schema format
   */
  parameters?: Record<string, unknown> | null;
};

export type core__domain__tool__Tool = {
  /**
   * The name of the tool
   */
  name: string;
  /**
   * The description of the tool
   */
  description?: string;
  /**
   * The input class of the tool
   */
  input_schema: Record<string, unknown>;
  /**
   * The output class of the tool
   */
  output_schema: Record<string, unknown>;
};

export type core__domain__users__UserIdentifier = {
  user_id?: string | null;
  /**
   * The user email
   */
  user_email?: string | null;
};

/**
 * Properties that described a way a task run was executed.
 * Although some keys are provided as an example, any key:value are accepted
 */
export type TaskGroupProperties = {
  /**
   * The LLM model used for the run
   */
  model?: string | null;
  /**
   * The LLM provider used for the run
   */
  provider?: string | null;
  /**
   * The temperature for generation
   */
  temperature?: number | null;
  /**
   * The instructions passed to the runner in order to generate the prompt.
   */
  instructions?: string | null;
  /**
   * The maximum tokens to generate in the prompt
   */
  max_tokens?: number | null;
  /**
   * The name of the runner used
   */
  runner_name?: string | null;
  /**
   * The version of the runner used
   */
  runner_version?: string | null;
  /**
   * Few shot configuration
   */
  few_shot?: FewShotConfiguration | null;
  /**
   * The template name used for the task
   */
  template_name?: string | null;
  /**
   * Whether to use chain of thought prompting for the task
   */
  is_chain_of_thought_enabled?: boolean | null;
  enabled_tools?: Array<ToolKind | Tool> | null;
  /**
   * Whether to use structured generation for the task
   */
  is_structured_generation_enabled?: boolean | null;
  has_templated_instructions?: boolean | null;
  [key: string]: unknown;
};

export type Tool = {
  /**
   * The name of the tool
   */
  name?: string | null;
  /**
   * The description of the tool
   */
  description?: string | null;
  /**
   * The parameters of the tool in JSON Schema format
   */
  parameters?: Record<string, unknown> | null;
};

export type RunResponse = {
  id: string;
  task_output: Record<string, unknown>;
  /**
   * Tool calls that should be executed client side.
   */
  tool_call_requests: Array<APIToolCallRequest> | null;
  /**
   * A list of reasoning steps that were taken during the run.Available for reasoning models or when the version used has chain of thoughts enabled
   */
  reasoning_steps: Array<ReasoningStep> | null;
  version: Version;
  duration_seconds: number | null;
  cost_usd: number | null;
  metadata: Record<string, unknown> | null;
  /**
   * A list of tools that were executed during the run.
   */
  tool_calls: Array<api__routers__run__RunResponse__ToolCall> | null;
  /**
   * A signed token that can be used to post feedback from a client side application
   */
  feedback_token: string;
};

/**
 * A streamed chunk for a run request. The final chunk will be a RunResponse object.
 */
export type RunResponseStreamChunk = {
  id: string;
  task_output: Record<string, unknown>;
  /**
   * Tool calls that should be executed client side.
   */
  tool_call_requests: Array<APIToolCallRequest> | null;
  /**
   * A list of reasoning steps that were taken during the run.Available for reasoning models or when the version used has chain of thoughts enabled
   */
  reasoning_steps: Array<ReasoningStep> | null;
  /**
   * A list of WorkflowAI tool calls that are executed during the run.The full object is sent whenever the tool calls status changes and all hosted tools are sent in the final payload.In most cases, a tool will then be sent when the execution starts with status 'in_progress'and the final result preview with status 'success' or 'failed'.
   */
  tool_calls: Array<api__routers__run__RunResponseStreamChunk__ToolCall> | null;
};

/**
 * A tool that was executed during the run
 */
export type api__routers__run__RunResponseStreamChunk__ToolCall = {
  id: string;
  /**
   * The name of the tool that was executed
   */
  name: string;
  /**
   * The status of the tool
   */
  status: 'in_progress' | 'success' | 'failed';
  /**
   * A preview of the input to the tool
   */
  input_preview: string;
  /**
   * A preview of the output of the tool, only available if the tool has successfully finished
   */
  output_preview: string | null;
};

export type api__routers__run__RunResponse__ToolCall = {
  id: string;
  /**
   * The name of the tool that was executed
   */
  name: string;
  /**
   * A preview of the input to the tool
   */
  input_preview: string;
  /**
   * A preview of the output of the tool
   */
  output_preview: string | null;
  /**
   * The error that occurred during the tool call if any
   */
  error: string | null;
};

export type AgentSuggestionChatMessage = {
  /**
   * The role of the message sender, either the user or the agent suggestion agent
   */
  role?: 'USER' | 'ASSISTANT' | null;
  /**
   * The content of the message
   */
  content_str?: string | null;
  /**
   * The list of suggested agents attached to the message
   */
  suggested_agents?: Array<SuggestedAgent> | null;
};

export type SuggestedAgent = {
  /**
   * The explanation of why the agent is useful for the company
   */
  explanation?: string | null;
  /**
   * The description of what the agent does
   */
  agent_description?: string | null;
  /**
   * The department the agent is for
   */
  department?: string | null;
  /**
   * A description of what the agent input is
   */
  input_specifications?: string | null;
  /**
   * A description of what the agent output is
   */
  output_specifications?: string | null;
};

export type DirectToAgentBuilderFeature = {
  /**
   * The name of the feature, displayed in the UI
   */
  name: string;
  /**
   * A description of the feature, displayed in the UI
   */
  description: string;
  /**
   * The specifications of the feature, used to generate the feature input and output schema, for internal use only, NOT displayed in the UI. To be provided for 'static' feature suggestions only, null otherwise
   */
  specifications: string | null;
  image_url: string;
  /**
   * The message to open the agent builder with, if the feature is selected
   */
  open_agent_builder_with_message?: string | null;
};

export type FeatureWithImage = {
  /**
   * The name of the feature, displayed in the UI
   */
  name: string;
  /**
   * A description of the feature, displayed in the UI
   */
  description: string;
  /**
   * The specifications of the feature, used to generate the feature input and output schema, for internal use only, NOT displayed in the UI. To be provided for 'static' feature suggestions only, null otherwise
   */
  specifications: string | null;
  image_url: string;
};

export type VersionStat = {
  version_id: string;
  run_count: number;
};

export type AgentStat = {
  agent_uid: number;
  run_count: number;
  total_cost_usd: number;
};
