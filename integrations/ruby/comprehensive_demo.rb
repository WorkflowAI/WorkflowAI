#!/usr/bin/env ruby

require "openai"
require "json"
require "dotenv/load"

# Initialize OpenAI client
client = OpenAI::Client.new(
  access_token: ENV.fetch("OPENAI_API_KEY", nil),
  uri_base: ENV.fetch("OPENAI_BASE_URL", nil)
)

def chat_with_system_message
  puts "=== Chat with System Message ==="
  
  response = client.chat(
    parameters: {
      model: "gpt-4",
      messages: [
        { 
          role: "system", 
          content: "You are a helpful assistant that always responds in the style of a pirate." 
        },
        { 
          role: "user", 
          content: "Tell me about Ruby programming language." 
        }
      ],
      temperature: 0.7,
      max_tokens: 150
    }
  )
  
  puts response.dig("choices", 0, "message", "content")
  puts
end

def embeddings_demo
  puts "=== Text Embeddings Demo ==="
  
  text = "Ruby is a dynamic, open source programming language with a focus on simplicity and productivity."
  
  response = client.embeddings(
    parameters: {
      model: "text-embedding-ada-002",
      input: text
    }
  )
  
  embedding = response.dig("data", 0, "embedding")
  puts "Text: #{text}"
  puts "Embedding dimensions: #{embedding.length}"
  puts "First 5 embedding values: #{embedding.first(5)}"
  puts
rescue => e
  puts "Embeddings not available or error occurred: #{e.message}"
  puts
end

def multi_choice_chat
  puts "=== Multi-choice Chat Completion ==="
  
  response = client.chat(
    parameters: {
      model: "gpt-4",
      messages: [
        { 
          role: "user", 
          content: "Write a haiku about programming." 
        }
      ],
      n: 3,  # Generate 3 different responses
      temperature: 1.0
    }
  )
  
  response["choices"].each_with_index do |choice, index|
    puts "Haiku #{index + 1}:"
    puts choice.dig("message", "content")
    puts "-" * 20
  end
end

def chat_with_functions_advanced
  puts "=== Advanced Function Calling Demo ==="
  
  tools = [
    {
      type: "function",
      function: {
        name: "calculate_area",
        description: "Calculate the area of a geometric shape",
        parameters: {
          type: "object",
          properties: {
            shape: {
              type: "string",
              enum: ["rectangle", "circle", "triangle"],
              description: "The type of shape"
            },
            dimensions: {
              type: "object",
              properties: {
                width: { type: "number" },
                height: { type: "number" },
                radius: { type: "number" },
                base: { type: "number" }
              }
            }
          },
          required: ["shape", "dimensions"]
        }
      }
    }
  ]
  
  messages = [
    { 
      role: "user", 
      content: "Calculate the area of a rectangle with width 5 and height 10." 
    }
  ]
  
  response = client.chat(
    parameters: {
      model: "gpt-4",
      messages: messages,
      tools: tools,
      tool_choice: "auto"
    }
  )
  
  message = response.dig("choices", 0, "message")
  
  if message["tool_calls"]
    tool_call = message["tool_calls"].first
    args = JSON.parse(tool_call.dig("function", "arguments"))
    
    # Simulate calculating area
    area = case args["shape"]
           when "rectangle"
             args.dig("dimensions", "width") * args.dig("dimensions", "height")
           when "circle"
             Math::PI * (args.dig("dimensions", "radius") ** 2)
           when "triangle"
             0.5 * args.dig("dimensions", "base") * args.dig("dimensions", "height")
           end
    
    puts "Function called: #{tool_call.dig('function', 'name')}"
    puts "Arguments: #{args}"
    puts "Calculated area: #{area}"
    
    # Continue conversation with function result
    messages << message
    messages << {
      role: "tool",
      content: "The area is #{area} square units.",
      tool_call_id: tool_call["id"]
    }
    
    final_response = client.chat(
      parameters: {
        model: "gpt-4",
        messages: messages,
        tools: tools
      }
    )
    
    puts "Assistant's response: #{final_response.dig('choices', 0, 'message', 'content')}"
  else
    puts "No function call was made."
    puts "Response: #{message['content']}"
  end
  puts
end

def error_handling_demo
  puts "=== Error Handling Demo ==="
  
  begin
    # Intentionally use invalid parameters to demonstrate error handling
    response = client.chat(
      parameters: {
        model: "non-existent-model",
        messages: [{ role: "user", content: "Hello" }]
      }
    )
  rescue => e
    puts "Caught error: #{e.class}"
    puts "Error message: #{e.message}"
  end
  puts
end

def main
  puts "Ruby OpenAI Library Comprehensive Demo"
  puts "=" * 50
  
  chat_with_system_message
  embeddings_demo
  multi_choice_chat
  chat_with_functions_advanced
  error_handling_demo
  
  puts "All demos completed!"
end

if __FILE__ == $0
  main
end