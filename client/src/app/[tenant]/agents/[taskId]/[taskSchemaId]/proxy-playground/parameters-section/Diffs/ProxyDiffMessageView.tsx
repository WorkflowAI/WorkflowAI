import { cn } from '@/lib/utils';
import { ProxyMessage } from '@/types/workflowAI';
import { ProxyMessageViewHeader } from '../../proxy-messages/ProxyMessageViewHeader';
import { ProxyFile } from '../../proxy-messages/components/ProxyFile';
import { ProxyTextarea } from '../../proxy-messages/components/ProxyTextarea';
import { ProxyToolCallRequest } from '../../proxy-messages/components/ProxyToolCallRequest';
import { ProxyToolCallResultView } from '../../proxy-messages/components/ProxyToolCallResult';
import { getExtendedMessageType } from '../../proxy-messages/utils';
import { ProxyDiffTextarea } from './ProxyDiffTextarea';

type Props = {
  message: ProxyMessage | undefined;
  oldMessage: ProxyMessage | undefined;
  inputVariblesKeys?: string[];
};

export function ProxyDiffMessageView(props: Props) {
  const { message, oldMessage, inputVariblesKeys } = props;

  const everythingWasRemoved = !message && !!oldMessage;
  const everythingWasAdded = !!message && !oldMessage;

  if (!message && !oldMessage) {
    return null;
  }

  const messageToUse = message ?? oldMessage;
  const showDiffTextarea = !!message && !!oldMessage;

  return (
    <div className='flex flex-col relative'>
      <div
        className={cn(
          'flex flex-col border border-gray-200 min-h-[50px] bg-white pb-3 rounded-[2px]',
          everythingWasRemoved && 'bg-red-100 border-red-200',
          everythingWasAdded && 'bg-green-100 border-green-300'
        )}
      >
        <ProxyMessageViewHeader
          type={getExtendedMessageType(messageToUse?.role ?? 'system', messageToUse?.content)}
          isHovering={false}
          avaibleTypes={[]}
          onRemove={undefined}
          onChangeType={() => {}}
          onAddContentEntry={() => {}}
          readonly={true}
        />
        <div className='flex flex-col gap-[10px]'>
          {messageToUse?.content.map((content, index) => {
            return (
              <div key={index} className='flex flex-col gap-[10px]'>
                {content.text !== undefined && !showDiffTextarea && (
                  <div className='flex w-full'>
                    <ProxyTextarea
                      key={index}
                      content={content}
                      setContent={() => {}}
                      placeholder='Message text content'
                      readOnly={true}
                      inputVariblesKeys={inputVariblesKeys}
                      supportInputVaribles={true}
                      supportObjectViewerIfPossible={false}
                    />
                  </div>
                )}
                {content.text !== undefined && showDiffTextarea && (
                  <div className='flex w-full'>
                    <ProxyDiffTextarea key={index} newText={content.text} oldText={oldMessage?.content[index].text} />
                  </div>
                )}
                {content.file && (
                  <div className='flex w-full px-3'>
                    <ProxyFile
                      content={content}
                      setContent={() => {}}
                      readonly={true}
                      onRemoveContentEntry={() => {}}
                    />
                  </div>
                )}
                {content.tool_call_request && (
                  <div className='flex w-full px-3'>
                    <ProxyToolCallRequest content={content} setContent={() => {}} readonly={true} />
                  </div>
                )}
                {content.tool_call_result && (
                  <div className='flex w-full px-3'>
                    <ProxyToolCallResultView result={content.tool_call_result} setContent={() => {}} readonly={true} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
