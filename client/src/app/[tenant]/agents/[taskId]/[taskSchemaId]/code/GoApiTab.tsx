'use client';

import { useMemo } from 'react';
import { CodeBlock } from '@/components/v2/CodeBlock';
import { PROD_RUN_URL } from '@/lib/constants';
import { TaskRun } from '@/types';
import { TaskID, TaskSchemaID, TenantID } from '@/types/aliases';
import { VersionEnvironment, VersionV1 } from '@/types/workflowAI';
import { versionForCodeGeneration } from './utils';

type GoApiTabProps = {
  tenant: TenantID;
  taskId: TaskID;
  taskSchemaId: TaskSchemaID;
  taskRun: TaskRun | undefined;
  environment?: VersionEnvironment;
  version: VersionV1;
  apiUrl: string | undefined;
};

export function GoApiTab(props: GoApiTabProps) {
  const { tenant, taskId, taskSchemaId, environment, taskRun: rawTaskRun, version, apiUrl } = props;

  const taskRunJSON = useMemo(() => JSON.stringify({ task_output: rawTaskRun?.task_output }, null, 2), [rawTaskRun]);

  const payload = useMemo(() => {
    if (!rawTaskRun) {
      return undefined;
    }
    const v = versionForCodeGeneration(environment, version);

    return {
      task_input: rawTaskRun.task_input,
      version: v,
      use_cache: 'auto',
    };
  }, [rawTaskRun, environment, version]);

  const payloadJSON = useMemo(() => JSON.stringify(payload, null, 2), [payload]);

  const installCode = useMemo(() => {
    return `go get github.com/workflowai/workflowai-go`;
  }, []);

  const code = useMemo(() => {
    if (!payload) return '';
    
    const host = apiUrl ?? PROD_RUN_URL;
    const formattedPayload = JSON.stringify(payload, null, 4);
    
    return `package main

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

type Input struct {
	TaskInput json.RawMessage \`json:"task_input"\`
	Version   string          \`json:"version"\`
	UseCache  string          \`json:"use_cache"\`
}

type Output struct {
	TaskOutput json.RawMessage \`json:"task_output"\`
}

func main() {
	// Replace with your WorkflowAI API key
	apiKey := "Add your API key here"

	// Create the request payload
	input := Input{
		TaskInput: json.RawMessage(\`${JSON.stringify(payload.task_input)}\`),
		Version:   "${payload.version}",
		UseCache:  "${payload.use_cache}",
	}

	// Convert the payload to JSON
	payload, err := json.Marshal(input)
	if err != nil {
		log.Fatalf("Error marshaling JSON: %v", err)
	}

	// Create the HTTP request
	url := "${host}/v1/${tenant}/tasks/${taskId}/schemas/${taskSchemaId}/run"
	req, err := http.NewRequestWithContext(context.Background(), http.MethodPost, url, bytes.NewBuffer(payload))
	if err != nil {
		log.Fatalf("Error creating request: %v", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer " + apiKey)

	// Send the request
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Fatalf("Error sending request: %v", err)
	}
	defer resp.Body.Close()

	// Read the response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		log.Fatalf("Error reading response: %v", err)
	}

	// Check if the request was successful
	if resp.StatusCode != http.StatusOK {
		log.Fatalf("Error: %s", body)
	}

	// Parse the response
	var output Output
	if err := json.Unmarshal(body, &output); err != nil {
		log.Fatalf("Error parsing response: %v", err)
	}

	// Pretty print the output
	prettyOutput, _ := json.MarshalIndent(output, "", "  ")
	fmt.Println(string(prettyOutput))
}

// Cache options:
// - "auto" (default): if a previous successful run is found and the temperature is set to 0, it will be used. Otherwise, the model is called.
// - "always": the cached output is returned when available, regardless of the temperature value
// - "never": the cache is never used`;
  }, [apiUrl, tenant, taskId, taskSchemaId, payload]);

  return (
    <div className='flex flex-col w-full h-full overflow-y-auto'>
      <CodeBlock language='Bash' snippet={installCode} />
      <CodeBlock language='Go' snippet={code} showTopBorder={true} />
      <CodeBlock language='JSON' snippet={taskRunJSON} showCopyButton={false} showTopBorder={true} />
    </div>
  );
} 