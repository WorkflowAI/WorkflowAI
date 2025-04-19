import json
import logging
import re
from typing import Any, NamedTuple

from core.domain.task_variant import SerializableTaskVariant

logger = logging.getLogger(__name__)


def generate_valid_function_name(original: str) -> str:
    """
    Generate a valid Go function name by removing leading digits from the given string.
    Returns the original string with leading digits removed, or 'func' if the result would be empty.
    """
    # Remove leading digits
    name = re.sub(r"^[\d\s]+", "", original)
    if name == "":
        return "func"

    return name


class GoCode(NamedTuple):
    client_setup: str
    code: str


def generate_go_code(
    task_variant: SerializableTaskVariant,
    example_task_run_input: dict[str, Any],
    version: str | int,
    url: str | None = None,
) -> GoCode:
    """Generate Go code for the given task variant"""
    
    task_id = task_variant.task_id
    schema_id = task_variant.task_schema_id
    
    # Convert input to JSON string for the example
    task_input_json = json.dumps(example_task_run_input or {}, indent=4)
    
    client_setup = """go get github.com/workflowai/workflowai-go"""

    code = f"""package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
)

type Input struct {{
	TaskInput json.RawMessage `json:"task_input"`
	Version   string          `json:"version"`
	UseCache  string          `json:"use_cache"`
}}

type Output struct {{
	TaskOutput json.RawMessage `json:"task_output"`
}}

func main() {{
	// Replace with your WorkflowAI API key
	apiKey := "Add your API key here"

	// Create the request payload
	input := Input{{
		TaskInput: json.RawMessage(`{task_input_json}`),
		Version:   "{version}",
		UseCache:  "auto",
	}}

	// Convert the payload to JSON
	payload, err := json.Marshal(input)
	if err != nil {{
		log.Fatalf("Error marshaling JSON: %v", err)
	}}

	// Create the HTTP request
	url := "{url or "https://api.workflowai.com"}/v1/${{TENANT}}/agents/{task_id}/schemas/{schema_id}/go"
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, bytes.NewBuffer(payload))
	if err != nil {{
		log.Fatalf("Error creating request: %v", err)
	}}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer " + apiKey)

	// Send the request
	client := &http.Client{{}}
	resp, err := client.Do(req)
	if err != nil {{
		log.Fatalf("Error sending request: %v", err)
	}}
	defer resp.Body.Close()

	// Read the response
	body, err := io.ReadAll(resp.Body)
	if err != nil {{
		log.Fatalf("Error reading response: %v", err)
	}}

	// Check if the request was successful
	if resp.StatusCode != http.StatusOK {{
		log.Fatalf("Error: %s", body)
	}}

	// Parse the response
	var output Output
	if err := json.Unmarshal(body, &output); err != nil {{
		log.Fatalf("Error parsing response: %v", err)
	}}

	// Pretty print the output
	prettyOutput, _ := json.MarshalIndent(output, "", "  ")
	fmt.Println(string(prettyOutput))
}}

// Cache options:
// - "auto" (default): if a previous successful run is found and the temperature is set to 0, it will be used. Otherwise, the model is called.
// - "always": the cached output is returned when available, regardless of the temperature value
// - "never": the cache is never used"""

    return GoCode(client_setup=client_setup, code=code) 