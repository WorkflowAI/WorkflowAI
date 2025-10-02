import { PlusIcon } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { useCopyToClipboard } from 'usehooks-ts';
import { Button } from '../ui/Button';
import { displaySuccessToaster } from '../ui/Sonner';
import { ProxyNewAgentClientCombobox } from './components/ProxyNewAgentClientCombobox';
import { ProxyNewAgentSectionHeader } from './components/ProxyNewAgentSectionHeader';

const allClients = ['Cursor', 'Windsurf', 'Claude Code', 'Github Copilot'];

export function ProxyNewAgentMCPFlowContent() {
  const [selectedClient, setSelectedClient] = useState<string | undefined>('Cursor');
  const [, copy] = useCopyToClipboard();

  const code = useMemo(() => {
    if (selectedClient === 'Claude Code') {
      return `claude mcp add workflowai https://api.workflowai.com/mcp/ --transport http -H "Authorization: Bearer YOUR_API_KEY_HERE"`;
    }

    return `{
    "mcpServers": {
      "workflowai": {
        "url": "https://api.workflowai.com/mcp/",
        "headers": {
          "Authorization": "Bearer <your API token here>"
        }
      }
    }
  }`;
  }, [selectedClient]);

  const onCopy = useCallback(() => {
    copy(code);
    displaySuccessToaster('Copied to clipboard');
  }, [code, copy]);

  const manualText = useMemo(() => {
    if (selectedClient === 'Cursor') {
      return (
        <>
          Or manually add the WorkflowAI MCP server to <span className='text-gray-700'>mcp.json</span>:
        </>
      );
    }
    if (selectedClient === 'Claude Code') {
      return <>{"Configure Claude Code to use WorkflowAI's MCP server:"}</>;
    }
    return (
      <>
        Add the WorkflowAI MCP server to <span className='text-gray-700'>mcp.json</span>:
      </>
    );
  }, [selectedClient]);

  return (
    <div className='flex flex-col bg-gray-50 rounded-[2px] w-full border border-gray-200 shadow-sm'>
      <div className='flex flex-col gap-2 bg-white p-4 shadow-sm'>
        <div className='text-gray-700 text-[13px] font-medium'>Select Your MCP Client</div>
        <ProxyNewAgentClientCombobox
          clients={allClients}
          selectedClient={selectedClient}
          setSelectedClient={setSelectedClient}
        />
      </div>
      <div className='flex flex-col w-full p-4'>
        <div className='text-gray-700 text-[16px] font-medium'>Installation</div>
        {selectedClient === 'Cursor' && (
          <div className='flex pt-2'>
            <Button
              variant='newDesign'
              icon={<PlusIcon className='w-4 h-4' />}
              className='bg-gray-700 text-white hover:text-white hover:bg-gray-800 font-medium'
            >{`Add WorkflowAI to ${selectedClient}`}</Button>
          </div>
        )}
        <div className='text-gray-500 text-[13px] font-normal pt-5 pb-2'>{manualText}</div>
        <div className='flex w-full bg-white rounded-[2px] border border-gray-200 relative'>
          <div className='p-3 whitespace-pre-wrap font-mono text-[13px] text-gray-600 pr-[75px]'>{code}</div>
          <Button variant='newDesignGray' size='sm' onClick={onCopy} className='absolute right-4 top-4'>
            Copy Code
          </Button>
        </div>
        <a
          className='text-gray-800 text-[13px] font-semibold underline cursor-pointer pt-5 pb-1'
          href='https://docs2.workflowai.com/'
          target='_blank'
        >
          Read the Full MCP Documentation
        </a>
      </div>
    </div>
  );
}

export function ProxyNewAgentMCPFlow() {
  return (
    <div className='flex gap-5 flex-col w-full h-full p-10 overflow-y-auto'>
      <ProxyNewAgentSectionHeader title='Set up the WorkflowAI MCP Server' number={1} />
      <ProxyNewAgentMCPFlowContent />
    </div>
  );
}
