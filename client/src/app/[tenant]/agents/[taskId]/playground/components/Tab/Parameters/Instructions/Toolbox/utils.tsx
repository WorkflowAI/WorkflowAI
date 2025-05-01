import { GlobeSearchRegular, WindowAdRegular } from '@fluentui/react-icons';
import { ToolKind } from '@/types/workflowAI';

export const allTools: ToolKind[] = ['@search-google', '@perplexity-sonar-pro', '@browser-text'];

export function getIcon(tool: ToolKind) {
  switch (tool) {
    case '@search-google':
    case '@perplexity-sonar-pro':
      return <GlobeSearchRegular className='w-[18px] h-[18px]' />;
    case '@browser-text':
      return <WindowAdRegular className='w-[18px] h-[18px]' />;
    default:
      return undefined;
  }
}

export function getToolName(tool: ToolKind) {
  switch (tool) {
    case '@search-google':
      return (
        <div>
          Search <span className='font-normal text-indigo-500'>(Google)</span>
        </div>
      );
    case '@perplexity-sonar-pro':
      return (
        <div>
          Search <span className='font-normal text-indigo-500'>(Perplexity)</span>
        </div>
      );
    case '@browser-text':
      return <div>Browser</div>;
    default:
      return <div>{tool}</div>;
  }
}

export function getSpecificToolName(tool: ToolKind) {
  switch (tool) {
    case '@search-google':
      return 'Google';
    case '@perplexity-sonar-pro':
      return 'Perplexity';
    default:
      return tool;
  }
}

export function getSpecificIconURL(tool: ToolKind) {
  switch (tool) {
    case '@search-google':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/GoogleSearchLogo.png';
    case '@perplexity-sonar-pro':
      return 'https://workflowai.blob.core.windows.net/workflowai-public/PerplexitySearchLogo.png';
    default:
      return undefined;
  }
}
