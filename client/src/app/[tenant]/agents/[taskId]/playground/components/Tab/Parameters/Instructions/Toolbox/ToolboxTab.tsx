import { GlobeSearchFilled, GlobeSearchRegular, WindowAdFilled } from '@fluentui/react-icons';
import { WindowAdRegular } from '@fluentui/react-icons';
import { ToolKind } from '@/types/workflowAI';

export type ToolboxTab = {
  tools: ToolKind[];
  name: string;
  iconOff: React.ReactNode;
  iconOn: React.ReactNode;
};

export const tabs: ToolboxTab[] = [
  {
    tools: ['@perplexity-sonar-pro', '@search-google'],
    name: 'Search',
    iconOff: <GlobeSearchRegular className='w-[18px] h-[18px]' />,
    iconOn: <GlobeSearchFilled className='w-[18px] h-[18px] text-indigo-700' />,
  },
  {
    tools: ['@browser-text'],
    name: 'Browser',
    iconOff: <WindowAdRegular className='w-[18px] h-[18px]' />,
    iconOn: <WindowAdFilled className='w-[18px] h-[18px] text-indigo-700' />,
  },
];
