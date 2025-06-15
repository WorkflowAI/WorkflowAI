import { WorkflowModelsTable } from './workflow-models-table';

interface ModelSupports {
  input_image: boolean;
  input_pdf: boolean;
  input_audio: boolean;
  output_image: boolean;
  output_text: boolean;
  audio_only: boolean;
  tool_calling: boolean;
  parallel_tool_calls: boolean;
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

async function getModels(): Promise<Model[]> {
  try {
    const response = await fetch('https://api.workflowai.com/v1/models', {
      // Cache for 1 hour, revalidate in background
      next: { revalidate: 3600 }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch models: ${response.statusText}`);
    }
    
    const data: ModelsResponse = await response.json();
    // Sort models by created date (newest first)
    return data.data.sort((a, b) => b.created - a.created);
  } catch (error) {
    console.error('Error fetching models:', error);
    // Return empty array on error to show empty table
    return [];
  }
}

export async function WorkflowModelsWrapper() {
  const models = await getModels();
  
  if (models.length === 0) {
    return (
      <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-4">
        <p className="text-muted-foreground">Unable to load models at this time. Please try again later.</p>
      </div>
    );
  }
  
  return <WorkflowModelsTable models={models} />;
} 