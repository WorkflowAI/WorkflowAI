import { useMemo } from 'react';
import { TaskTemperatureView } from '@/components/v2/TaskTemperatureBadge';
import { useCopy } from '@/lib/hooks/useCopy';
import { ProxyMessagesView } from '../proxy-playground/proxy-messages/ProxyMessagesView';
import { InstructionTooltip } from './InstructionTooltip';
import { VersionEntry } from './utils';

type VersionEntryContainerPropertiesProps = {
  entry: VersionEntry;
};

export function VersionEntryContainerProperties(props: VersionEntryContainerPropertiesProps) {
  const { entry } = props;

  const onCopy = useCopy();

  const messages = useMemo(() => {
    if (!entry.majorVersion.properties.messages) {
      return undefined;
    }
    const messages = entry.majorVersion.properties.messages;
    if (messages.length === 0) {
      return undefined;
    }
    return messages;
  }, [entry.majorVersion.properties.messages]);

  const instructions = useMemo(() => {
    if (!entry.majorVersion.properties.instructions) {
      return undefined;
    }

    const instructions = entry.majorVersion.properties.instructions;
    if (instructions === undefined || instructions.length === 0) {
      return undefined;
    }

    return instructions;
  }, [entry.majorVersion.properties.instructions]);

  return (
    <div className='flex flex-col flex-1 border-l border-gray-200 border-dashed pt-3 pb-3 px-4 gap-3'>
      {!!messages ? (
        <div className='max-h-[calc(100vh-260px)] overflow-y-auto'>
          <ProxyMessagesView messages={messages} />
        </div>
      ) : (
        !!instructions && (
          <div className='flex flex-col gap-1.5'>
            <div className='text-gray-900 text-[13px] font-medium'>Instructions:</div>
            <InstructionTooltip onCopy={() => onCopy(instructions)}>
              <div className='text-gray-900 text-[13px] font-normal px-3 py-2 bg-white rounded-[2px] border border-gray-200 whitespace-pre-wrap max-h-[calc(100vh-260px)] overflow-y-auto'>
                {instructions}
              </div>
            </InstructionTooltip>
          </div>
        )
      )}
      <div className='flex flex-col gap-0.5'>
        <div className='text-gray-900 text-[13px] font-medium'>Temperature:</div>
        <div>
          <TaskTemperatureView
            temperature={entry.majorVersion.properties.temperature}
            className='text-gray-900 gap-0.5'
          />
        </div>
      </div>
    </div>
  );
}
