# Frameworks Tests

This directory contains tests for the different frameworks that we should support through the OpenAI Proxy.

Each directory should contain a `README.md` that includes instructions on how to install the framework and
run each script.

## Available Languages

- **Go** (`golang/`) - OpenAI integration tests using the official openai-go library
- **JavaScript/TypeScript** (`js/`) - OpenAI integration tests using the openai npm package  
- **Ruby** (`ruby/`) - OpenAI integration tests using the ruby-openai gem
- **Rust** (`rust/`) - Rust integration tests

Each language implementation includes examples for:
- Basic chat completions (streaming and non-streaming)
- Function/tool calling
- Advanced API features
- Error handling
