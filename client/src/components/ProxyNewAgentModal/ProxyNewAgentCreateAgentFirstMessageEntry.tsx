import { ArrowUpFilled } from '@fluentui/react-icons';
import cx from 'classnames';
import { useState } from 'react';
import { WorkflowAIIcon } from '../Logos/WorkflowAIIcon';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Textarea';

type Props = {
  sendMessage: (message: string) => void;
};

export function ProxyNewAgentCreateAgentFirstMessageEntry(props: Props) {
  const { sendMessage } = props;

  const [localMessage, setLocalMessage] = useState('');

  const handleSendMessage = () => {
    sendMessage(localMessage);
    setLocalMessage('');
  };

  return (
    <div className='flex flex-col gap-6 w-full px-6 items-center justify-center'>
      <WorkflowAIIcon className='shrink-0 w-16 h-16' />
      <div className='text-[18px] text-gray-500 font-normal'>
        What <span className='text-gray-700 font-medium'>AI agent</span> would you like to build?
      </div>
      <div className='flex w-full rounded-[4px] bg-custom-gradient-solid shadow-md max-w-[1000px]'>
        <div className='flex flex-row w-full items-end justify-between gap-2 rounded-[2px] m-[2px] px-2 py-1 bg-white'>
          <Textarea
            value={localMessage}
            onChange={(event) => setLocalMessage(event.target.value)}
            placeholder='Write a description of the agent you want to build.'
            className='w-full text-[16px] font-normal pt-2 pb-[6px] pr-0 pl-1 focus-visible:ring-0 border-none bg-transparent max-h-[300px] scrollbar-hide text-gray-900'
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                if (localMessage.length > 0) {
                  handleSendMessage();
                }
              }
            }}
            autoFocus={true}
          />
          <Button
            variant='newDesignIndigo'
            icon={<ArrowUpFilled className='w-3.5 h-3.5' />}
            size='none'
            className={cx(
              'w-8 h-8 rounded-full flex-shrink-0 disabled:text-gray-400 disabled:opacity-100 mb-1',
              localMessage.length === 0 ? 'bg-gray-100 disabled:bg-gray-100' : 'bg-custom-indigo-gradient'
            )}
            disabled={localMessage.length === 0}
            onClick={handleSendMessage}
          />
        </div>
      </div>
    </div>
  );
}
