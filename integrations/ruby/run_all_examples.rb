#!/usr/bin/env ruby

require "dotenv/load"

# List of example scripts to run
EXAMPLES = [
  "demo.rb",
  "streaming_demo.rb", 
  "chat_completion_tool_calling.rb",
  "comprehensive_demo.rb"
]

def run_example(script)
  puts "\n" + "=" * 60
  puts "Running: #{script}"
  puts "=" * 60
  
  success = system("bundle exec ruby #{script}")
  
  if success
    puts "\n✅ #{script} completed successfully"
  else
    puts "\n❌ #{script} failed with exit code #{$?.exitstatus}"
  end
  
  success
end

def main
  puts "Ruby OpenAI Integration Tests Runner"
  puts "Running all example scripts..."
  
  # Check if bundle install has been run
  unless File.exist?("Gemfile.lock")
    puts "\n📦 Installing dependencies first..."
    system("bundle install")
  end
  
  results = {}
  
  EXAMPLES.each do |script|
    results[script] = run_example(script)
    
    # Add a pause between scripts
    sleep(1)
  end
  
  puts "\n" + "=" * 60
  puts "SUMMARY"
  puts "=" * 60
  
  results.each do |script, success|
    status = success ? "✅ PASS" : "❌ FAIL"
    puts "#{status} - #{script}"
  end
  
  failed_count = results.values.count(false)
  total_count = results.size
  
  puts "\nTotal: #{total_count}, Passed: #{total_count - failed_count}, Failed: #{failed_count}"
  
  if failed_count > 0
    puts "\n⚠️  Some tests failed. Check the output above for details."
    exit(1)
  else
    puts "\n🎉 All tests passed!"
  end
end

if __FILE__ == $0
  main
end