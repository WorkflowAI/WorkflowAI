import { ToolKind } from '@/types/workflowAI';
import { ToolboxBrowserMenu } from './ToolboxBrowserMenu';
import { ToolboxSearchMenu } from './ToolboxSearchMenu';
import { ToolboxTab } from './ToolboxTab';

type ToolboxModalTabContentProps = {
  tab: ToolboxTab;
  tools: Set<ToolKind>;
  setTools: React.Dispatch<React.SetStateAction<Set<ToolKind>>>;
};

export function ToolboxModalTabContent(props: ToolboxModalTabContentProps) {
  const { tab, tools, setTools } = props;

  switch (tab.name) {
    case 'Browser':
      return <ToolboxBrowserMenu tab={tab} tools={tools} setTools={setTools} />;
    case 'Search':
      return <ToolboxSearchMenu tab={tab} tools={tools} setTools={setTools} />;
    default:
      return null;
  }
}
