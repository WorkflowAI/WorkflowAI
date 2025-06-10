# Ruby Integration Scripts

## Requirements

- Ruby 3.0+
- Bundler gem

## Setup

1. Install dependencies:
   ```bash
   bundle install
   ```

2. Set environment variables (optional - will use defaults if not set):
   ```bash
   export OPENAI_BASE_URL="your-workflowai-api-url/v1"
   export OPENAI_API_KEY="your-workflowai-api-key"
   ```

## Structure

- Each example is a Ruby script file.
- The examples demonstrate different OpenAI API functionalities using the ruby-openai gem.
- Run examples using: `bundle exec ruby <example>.rb`

## Examples

### Basic Chat Completion
```bash
bundle exec ruby demo.rb
```

### Chat Completion with Function/Tool Calling
```bash
bundle exec ruby chat_completion_tool_calling.rb
```

### Streaming Chat Completion
```bash
bundle exec ruby streaming_demo.rb
```

## Notes

- The examples use the `ruby-openai` gem to interact with the OpenAI API
- Scripts will use environment variables `OPENAI_BASE_URL` and `OPENAI_API_KEY` if set
- If environment variables are not set, the scripts will use OpenAI's default endpoints