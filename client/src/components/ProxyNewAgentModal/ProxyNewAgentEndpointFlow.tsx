import { ProxyNewAgentPromptComponent } from './components/ProxyNewAgentPromptComponent';
import { ProxyNewAgentSectionHeader } from './components/ProxyNewAgentSectionHeader';

export function ProxyNewAgentEndpointFlow() {
  return (
    <div className='flex flex-col w-full h-full p-10 gap-5 overflow-y-auto'>
      <ProxyNewAgentSectionHeader title='Add Your Agent to WorkflowAI' number={2} />
      <ProxyNewAgentPromptComponent
        title='Create New AI Agent'
        description='The MCP connects your IDE to WorkflowAI so you can create agents without leaving your editor.'
        imageURL='https://workflowai.blob.core.windows.net/workflowai-public/CreateNewAgentIllustration.png'
        prompt='I want to use WorkflowAI to build a feature that extracts flights information from an email'
      />
      <ProxyNewAgentPromptComponent
        title='Import Existing AI Agent'
        description='With the MCP, you can bring over your agents without starting from scratch.'
        imageURL='https://workflowai.blob.core.windows.net/workflowai-public/ImportExistingAgentIllustration.png'
        prompt='Migrate this agent to WorkflowAI'
      />
    </div>
  );
}
