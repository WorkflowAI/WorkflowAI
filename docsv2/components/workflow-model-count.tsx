interface ModelSupports {
  input_image: boolean;
  input_pdf: boolean;
  input_audio: boolean;
  output_image: boolean;
  output_text: boolean;
  audio_only: boolean;
  support_input_schema: boolean;
  parallel_tool_calls: boolean;
  tool_calling: boolean;
}

interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
  display_name: string;
  icon_url: string;
  supports: ModelSupports;
}

interface ModelsResponse {
  object: string;
  data: Model[];
}

async function getModelsCount(): Promise<number> {
  try {
    const response = await fetch('https://api.workflowai.com/v1/models', {
      // Cache for 1 hour, revalidate in background
      next: { revalidate: 3600 }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch models: ${response.statusText}`);
    }
    
    const data: ModelsResponse = await response.json();
    return data.data.length;
  } catch (error) {
    console.error('Error fetching models count:', error);
    // Return fallback count on error
    return 100;
  }
}

export async function WorkflowModelCount() {
  const count = await getModelsCount();
  
  return <>{count}+</>;
} 