#!/usr/bin/env ruby

require "openai"
require "dotenv/load"

# Initialize OpenAI client
client = OpenAI::Client.new(
  access_token: ENV.fetch("OPENAI_API_KEY", nil),
  uri_base: ENV.fetch("OPENAI_BASE_URL", nil)
)

def streaming_demo
  puts "=== Streaming Chat Completion Demo ==="
  puts "Question: Tell me a short story about a robot learning to paint."
  puts "\nStreaming response:"
  puts "-" * 50
  
  client.chat(
    parameters: {
      model: "gpt-4",
      messages: [
        { 
          role: "user", 
          content: "Tell me a short story about a robot learning to paint." 
        }
      ],
      stream: proc do |chunk, _bytesize|
        content = chunk.dig("choices", 0, "delta", "content")
        print content if content
        
        # Check if streaming is done
        finish_reason = chunk.dig("choices", 0, "finish_reason")
        if finish_reason == "stop"
          puts "\n" + "-" * 50
          puts "Streaming completed."
        end
      end
    }
  )
end

def conversation_demo  
  puts "\n\n=== Multi-turn Conversation with Streaming ==="
  
  messages = [
    { role: "system", content: "You are a helpful assistant that speaks concisely." }
  ]
  
  questions = [
    "What is Ruby programming language?",
    "What are its main advantages?", 
    "Can you give me a simple Ruby code example?"
  ]
  
  questions.each_with_index do |question, index|
    puts "\nQuestion #{index + 1}: #{question}"
    puts "Response:"
    puts "-" * 30
    
    messages << { role: "user", content: question }
    
    response_content = ""
    
    client.chat(
      parameters: {
        model: "gpt-4",
        messages: messages,
        stream: proc do |chunk, _bytesize|
          content = chunk.dig("choices", 0, "delta", "content")
          if content
            print content
            response_content += content
          end
        end
      }
    )
    
    # Add assistant's response to conversation history
    messages << { role: "assistant", content: response_content }
    puts "\n" + "-" * 30
  end
end

def main
  streaming_demo
  conversation_demo
  puts "\nDemo completed!"
end

if __FILE__ == $0
  main
end