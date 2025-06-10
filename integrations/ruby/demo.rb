#!/usr/bin/env ruby

require "openai"
require "dotenv/load"

# Initialize OpenAI client
# Uses OPENAI_API_KEY and OPENAI_BASE_URL from environment variables if set
client = OpenAI::Client.new(
  access_token: ENV.fetch("OPENAI_API_KEY", nil),
  uri_base: ENV.fetch("OPENAI_BASE_URL", nil)
)

def main
  puts "=== Basic Chat Completion (Non-streaming) ==="
  
  # Non-streaming chat completion
  response = client.chat(
    parameters: {
      model: "gpt-4",
      messages: [{ role: "user", content: "Say this is a test" }]
    }
  )
  
  puts response.dig("choices", 0, "message", "content")
  puts

  puts "=== Streaming Chat Completion ==="
  
  # Streaming chat completion
  client.chat(
    parameters: {
      model: "gpt-4", 
      messages: [{ role: "user", content: "Say this is a test" }],
      stream: proc do |chunk, _bytesize|
        content = chunk.dig("choices", 0, "delta", "content")
        print content if content
      end
    }
  )
  
  puts # New line after streaming
end

if __FILE__ == $0
  main
end