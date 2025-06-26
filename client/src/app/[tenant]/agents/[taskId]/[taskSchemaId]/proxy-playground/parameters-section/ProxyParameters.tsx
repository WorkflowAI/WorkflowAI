import { Loader2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { TemperatureSelector } from '@/components/TemperatureSelector/TemperatureSelector';
import { Button } from '@/components/ui/Button';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { ProxyMajorVersionDetails } from '@/components/v2/ProxyMajorVersionDetails';
import { ExtractTempleteError } from '@/store/extract_templete';
import { MajorVersion, ProxyMessage, ToolKind, Tool_Output, VersionV1 } from '@/types/workflowAI';
import { MajorVersionCombobox } from '../../playground/components/MajorVersionSelector/MajorVersionSelector';
import { ProxyImproveMessagesControls } from '../hooks/useProxyImproveMessages';
import { AdvancedSettings } from '../hooks/useProxyPlaygroundSearchParams';
import { ProxyMessagesView } from '../proxy-messages/ProxyMessagesView';
import { getAvaibleMessageTypes } from '../proxy-messages/utils';
import { AdvancedSettingsView } from './AdvancedSettings/AdvancedSettingsView';
import { ProxyDiffMessagesView } from './Diffs/ProxyDiffMessagesView';
import { ProxyDiffsHeader } from './Diffs/ProxyDiffsHeader';
import { ProxyTools } from './ProxyTools';

type ProxyParametersProps = {
  messages: ProxyMessage[] | undefined;
  setMessages: (messages: ProxyMessage[] | undefined) => void;

  advancedSettings: AdvancedSettings;

  toolCalls: (ToolKind | Tool_Output)[] | undefined;
  setToolCalls: (toolCalls: (ToolKind | Tool_Output)[] | undefined) => void;

  majorVersions: MajorVersion[];
  matchedMajorVersion: MajorVersion | undefined;
  useParametersFromMajorVersion: (version: MajorVersion) => void;

  showSaveAllVersions: boolean;
  onSaveAllVersions: () => void;
  versionsForRuns: Record<string, VersionV1>;

  inputVariblesKeys: string[] | undefined;
  error: ExtractTempleteError | undefined;

  improveMessagesControls: ProxyImproveMessagesControls;

  maxTokens: number | undefined;
};

export function ProxyParameters(props: ProxyParametersProps) {
  const {
    messages,
    setMessages,
    advancedSettings,
    toolCalls,
    setToolCalls,
    majorVersions,
    matchedMajorVersion,
    useParametersFromMajorVersion,
    showSaveAllVersions,
    onSaveAllVersions,
    versionsForRuns,
    inputVariblesKeys,
    error,
    improveMessagesControls,
    maxTokens,
  } = props;

  const version = useMemo(() => {
    const keys = Object.keys(versionsForRuns);
    if (keys.length === 0) {
      return undefined;
    }
    return versionsForRuns[keys[0]];
  }, [versionsForRuns]);

  const [isAnyTextareaFocused, setIsAnyTextareaFocused] = useState(false);

  return (
    <div className='flex flex-col w-full h-full'>
      {error && !isAnyTextareaFocused && (
        <div className='absolute top-[40px] right-0 -translate-x-[88px] translate-y-[4px] bg-red-500 flex rounded-[2px] border border-red-600 shadow-lg py-1 px-2 z-10'>
          <div className='text-white text-[13px] whitespace-pre-wrap'>{error.message}</div>
        </div>
      )}

      <div className='flex flex-row h-[48px] w-full justify-between items-center shrink-0 border-b border-gray-200 border-dashed px-4'>
        <div className='flex flex-row items-center gap-2'>
          {improveMessagesControls.isImproving && (
            <div className='flex items-center justify-center'>
              <Loader2 className='w-4 h-4 animate-spin text-gray-700' />
            </div>
          )}
          <div className='flex items-center font-semibold text-[16px] text-gray-700'>Version</div>
          {showSaveAllVersions && version && (
            <SimpleTooltip
              content={<ProxyMajorVersionDetails version={version} />}
              tooltipClassName='w-[350px] p-0 rounded-[2px] border border-gray-200'
              tooltipDelay={100}
              side='bottom'
              align='start'
            >
              <Button variant='newDesign' size='sm' onClick={onSaveAllVersions}>
                Save
              </Button>
            </SimpleTooltip>
          )}
        </div>
        <div className='flex w-full justify-end'>
          <MajorVersionCombobox
            majorVersions={majorVersions}
            matchedMajorVersion={matchedMajorVersion}
            useParametersFromMajorVersion={useParametersFromMajorVersion}
          />
        </div>
      </div>
      <div className='relative flex flex-col w-full flex-1 overflow-hidden'>
        <div className='flex flex-col w-full h-full overflow-y-auto'>
          {improveMessagesControls.oldProxyMessages && improveMessagesControls.showDiffChangelog && (
            <div className='flex w-full h-max px-4 pt-4'>
              <ProxyDiffsHeader improveMessagesControls={improveMessagesControls} />
            </div>
          )}
          {improveMessagesControls.oldProxyMessages && improveMessagesControls.showDiffs ? (
            <ProxyDiffMessagesView
              messages={messages}
              oldMessages={improveMessagesControls.oldProxyMessages}
              className='px-4 py-4 min-h-[100px]'
              inputVariblesKeys={inputVariblesKeys}
            />
          ) : (
            <ProxyMessagesView
              messages={messages}
              setMessages={setMessages}
              defaultType={getAvaibleMessageTypes('version')[0]}
              avaibleTypes={getAvaibleMessageTypes('version')}
              className='px-4 py-4 min-h-[100px]'
              allowRemovalOfLastMessage={false}
              inputVariblesKeys={inputVariblesKeys}
              onAnyTextareaFocusChange={setIsAnyTextareaFocused}
            />
          )}
        </div>
      </div>
      <div className='flex flex-col w-full border-t border-gray-200 border-dashed'>
        <div className='flex flex-col gap-1 px-4 pt-2 pb-3 border-b border-gray-200 border-dashed'>
          <div className='flex w-full items-center font-medium text-[13px] text-gray-900'>Tools</div>
          <ProxyTools
            toolCalls={toolCalls}
            setToolCalls={setToolCalls}
            messages={messages}
            onToolsChange={improveMessagesControls.updateToolsInVersionMessages}
          />
        </div>
        <div className='flex flex-row w-full items-center'>
          <div className='flex flex-col gap-1 px-4 pt-3 pb-3'>
            <div className='flex w-full items-center font-medium text-[13px] text-gray-900'>Temperature</div>
            <TemperatureSelector
              temperature={advancedSettings.temperature ? Number(advancedSettings.temperature) : 0}
              setTemperature={(temperature) => advancedSettings.setTemperature(String(temperature))}
            />
          </div>
          <AdvancedSettingsView advancedSettings={advancedSettings} maxTokens={maxTokens} />
        </div>
      </div>
    </div>
  );
}
