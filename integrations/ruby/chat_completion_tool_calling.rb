#!/usr/bin/env ruby

require "openai"
require "json"
require "dotenv/load"

# Initialize OpenAI client
client = OpenAI::Client.new(
  access_token: ENV.fetch("OPENAI_API_KEY", nil),
  uri_base: ENV.fetch("OPENAI_BASE_URL", nil)
)

# Mock function to simulate weather data retrieval
def get_weather(location)
  # In a real implementation, this function would call a weather API
  "Sunny, 25°C"
end

def main
  question = "What is the weather in New York City?"
  
  puts "> #{question}"
  
  messages = [
    { role: "user", content: question }
  ]
  
  tools = [
    {
      type: "function",
      function: {
        name: "get_weather",
        description: "Get weather at the given location",
        parameters: {
          type: "object",
          properties: {
            location: {
              type: "string"
            }
          },
          required: ["location"]
        }
      }
    }
  ]
  
  # Make initial chat completion request
  response = client.chat(
    parameters: {
      model: "gpt-4o",
      messages: messages,
      tools: tools
    }
  )
  
  message = response.dig("choices", 0, "message")
  tool_calls = message["tool_calls"]
  
  # Return early if there are no tool calls
  if tool_calls.nil? || tool_calls.empty?
    puts "No function call"
    return
  end
  
  # If there was a function call, continue the conversation
  messages << message
  
  tool_calls.each do |tool_call|
    if tool_call.dig("function", "name") == "get_weather"
      # Extract the location from the function call arguments
      args = JSON.parse(tool_call.dig("function", "arguments"))
      location = args["location"]
      
      # Simulate getting weather data
      weather_data = get_weather(location)
      
      # Print the weather data
      puts "Weather in #{location}: #{weather_data}"
      
      # Add the tool response to messages
      messages << {
        role: "tool",
        content: weather_data,
        tool_call_id: tool_call["id"]
      }
    end
  end
  
  # Make final completion request with tool response
  final_response = client.chat(
    parameters: {
      model: "gpt-4o",
      messages: messages,
      tools: tools
    }
  )
  
  puts final_response.dig("choices", 0, "message", "content")
end

if __FILE__ == $0
  main
end