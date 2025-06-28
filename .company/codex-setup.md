# Codex Setup in ChatGPT

## Connecting to the WorkflowAI Repository

1. Go to [chatgpt.com](https://chatgpt.com/) and select **Codex** from the left sidebar
2. If this is your first time using Codex, follow the prompts to connect your GitHub account
3. Ensure your GitHub account has access to the **WorkflowAI/WorkflowAI** repository
4. Once connected, proceed with setting up the environments as described below

## Setting Up the Python Environment

1. Click the **Environments** tab in the top navigation bar
2. Select **Create environment**
3. In the environment setup screen:
   - **Repository**: Choose **WorkflowAI/WorkflowAI**
   - **Name**: Enter `workflowai/python`
   - **Image**: Set to `universal`
   - **Agent internet access**: Set to **On** with domain allow list set to **common dependencies**
   - **Setup script**: Add the following:
```bash
corepack enable
corepack prepare yarn@stable --activate
yarn -v
# yarn install
poetry install
```

## Setting Up the TypeScript Environment

1. Click the **Environments** tab in the top navigation bar
2. Select **Create environment**
3. In the environment setup screen:
   - **Repository**: Choose **WorkflowAI/WorkflowAI**
   - **Name**: Enter `workflowai/typescript`
   - **Image**: Set to `universal`
   - **Agent internet access**: Set to **On** with domain allow list set to **common dependencies**
   - **Setup script**: Add the following:
```bash
corepack enable
corepack prepare yarn@stable --activate
yarn -v
yarn install
# poetry install
```

Once both environments are created, you'll be able to use them for working with the WorkflowAI repository in Codex.
