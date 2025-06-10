package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"

	"github.com/sashabaranov/go-openai"
)

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

	// Create a streaming chat completion request
	req := openai.ChatCompletionRequest{
		Model: openai.GPT3Dot5Turbo,
		Messages: []openai.ChatCompletionMessage{
			{
				Role:    openai.ChatMessageRoleUser,
				Content: "Please write a short poem about programming",
			},
		},
		MaxTokens: 200,
		Stream:    true,
	}

	// Create the streaming request
	stream, err := client.CreateChatCompletionStream(context.Background(), req)
	if err != nil {
		log.Fatalf("ChatCompletionStream error: %v", err)
	}
	defer stream.Close()

	fmt.Print("Streaming response: ")

	// Read from the stream
	for {
		response, err := stream.Recv()
		if err == io.EOF {
			fmt.Println("\nStream finished")
			break
		}

		if err != nil {
			log.Fatalf("Stream error: %v", err)
		}

		// Print the content as it arrives
		if len(response.Choices) > 0 {
			content := response.Choices[0].Delta.Content
			fmt.Print(content)
		}
	}
}