package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/sashabaranov/go-openai"
	"github.com/sashabaranov/go-openai/jsonschema"
)

// getCurrentWeather is a mock function that simulates getting weather data
func getCurrentWeather(location string, unit string) string {
	weatherData := map[string]interface{}{
		"location":    location,
		"temperature": "22",
		"unit":        unit,
		"forecast":    "Sunny",
	}
	
	result, _ := json.Marshal(weatherData)
	return string(result)
}

func main() {
	// Get API key and base URL from environment variables
	apiKey := os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		log.Fatal("OPENAI_API_KEY environment variable is required")
	}

	baseURL := os.Getenv("OPENAI_BASE_URL")
	if baseURL == "" {
		baseURL = "https://api.openai.com/v1"
	}

	// Create OpenAI client
	config := openai.DefaultConfig(apiKey)
	config.BaseURL = baseURL
	client := openai.NewClientWithConfig(config)

	// Define the function tool
	tools := []openai.Tool{
		{
			Type: openai.ToolTypeFunction,
			Function: &openai.FunctionDefinition{
				Name:        "get_current_weather",
				Description: "Get the current weather in a given location",
				Parameters: jsonschema.Definition{
					Type: jsonschema.Object,
					Properties: map[string]jsonschema.Definition{
						"location": {
							Type:        jsonschema.String,
							Description: "The city and state, e.g. San Francisco, CA",
						},
						"unit": {
							Type: jsonschema.String,
							Enum: []string{"celsius", "fahrenheit"},
						},
					},
					Required: []string{"location"},
				},
			},
		},
	}

	// Create a chat completion request with tool calling
	req := openai.ChatCompletionRequest{
		Model: openai.GPT3Dot5Turbo,
		Messages: []openai.ChatCompletionMessage{
			{
				Role:    openai.ChatMessageRoleUser,
				Content: "What's the weather like in Boston?",
			},
		},
		Tools:    tools,
		MaxTokens: 300,
	}

	// Make the request
	resp, err := client.CreateChatCompletion(context.Background(), req)
	if err != nil {
		log.Fatalf("ChatCompletion error: %v", err)
	}

	// Check if the model wants to call a function
	if len(resp.Choices) > 0 {
		choice := resp.Choices[0]
		
		if len(choice.Message.ToolCalls) > 0 {
			// Handle function call
			for _, toolCall := range choice.Message.ToolCalls {
				if toolCall.Function.Name == "get_current_weather" {
					var args map[string]interface{}
					json.Unmarshal([]byte(toolCall.Function.Arguments), &args)
					
					location := args["location"].(string)
					unit := "celsius"
					if u, ok := args["unit"].(string); ok {
						unit = u
					}
					
					// Call the function
					result := getCurrentWeather(location, unit)
					
					fmt.Printf("Function called: %s\n", toolCall.Function.Name)
					fmt.Printf("Arguments: %s\n", toolCall.Function.Arguments)
					fmt.Printf("Result: %s\n", result)
				}
			}
		} else {
			fmt.Printf("Response: %s\n", choice.Message.Content)
		}
	} else {
		fmt.Println("No response received")
	}
}