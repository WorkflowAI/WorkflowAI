import { useMemo } from 'react';
import { ModelOutputErrorInformation } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/playground/components/ModelOutputErrorInformation';
import { ProxyMessagesView } from '@/app/[tenant]/agents/[taskId]/[taskSchemaId]/proxy-playground/proxy-messages/ProxyMessagesView';
import { ProxyMessage, api__routers__runs_v1__RunV1__Error } from '@/types/workflowAI';

type Props = {
  messages: ProxyMessage[] | undefined;
  error: api__routers__runs_v1__RunV1__Error | undefined;
  supportOpeningInPlayground?: boolean;
};

export function ProxyRunDetailsMessagesView(props: Props) {
  const { messages, error, supportOpeningInPlayground } = props;

  const plainError = useMemo(() => {
    if (!error) {
      return undefined;
    }

    return new Error(error?.message);
  }, [error]);

  const headerText = !messages || messages.length <= 1 ? 'Output' : 'Conversation';

  return (
    <div className='flex flex-col h-full w-full overflow-hidden'>
      <div className='flex w-full h-12 border-b border-dashed border-gray-200 items-center px-4'>
        <div className='text-[16px] font-semibold text-gray-700'>{headerText}</div>
      </div>
      <div className='flex flex-col w-full max-h-[calc(100%-48px)] overflow-y-auto py-2.5'>
        {!!plainError && (
          <div className='flex flex-col w-full items-center px-4 pb-20 flex-shrink-0'>
            <ModelOutputErrorInformation errorForModel={plainError} />
          </div>
        )}
        <ProxyMessagesView
          messages={messages as ProxyMessage[]}
          className='flex w-full h-max px-4 py-2'
          supportRunDetails={true}
          supportOpeningInPlayground={supportOpeningInPlayground}
          scrollToLastMessage={true}
        />
      </div>
    </div>
  );
}
