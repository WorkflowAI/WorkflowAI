import { ArrowClockwise16Regular } from '@fluentui/react-icons';
import { FeedbackButtons } from '@workflowai/react';
import dayjs from 'dayjs';
import { useAuth } from '@/lib/AuthContext';
import { WORKFLOW_AI_USERNAME } from '@/lib/constants';
import { WorkflowAIIcon } from '../Logos/WorkflowAIIcon';
import { Avatar, AvatarImage } from '../ui/Avatar/Avatar';
import { Button } from '../ui/Button';
import { MarkdownMessageTextView } from './MarkdownMessageTextView';

export type ConversationMessage = {
  message: string | React.ReactNode;
  username: string;
  date?: Date;
  imageUrl?: string;
  streamed?: boolean;
  component?: React.ReactNode;
  feedbackToken?: string | null;
};

type MessageAvatarProps = {
  imageUrl?: string | undefined;
  username: string;
};

function MessageAvatar(props: MessageAvatarProps) {
  const { imageUrl, username } = props;

  if (imageUrl) {
    return (
      <Avatar className='h-6 w-6'>
        <AvatarImage src={imageUrl} />
      </Avatar>
    );
  }

  return (
    <div className='w-6 h-6 flex items-center justify-center rounded-full border border-gray-200 shrink-0'>
      {username === WORKFLOW_AI_USERNAME ? <WorkflowAIIcon className='w-3 h-3' /> : username[0].toUpperCase()}
    </div>
  );
}

type TaskConversationRetryCellProps = {
  retry: () => void;
};

export function TaskConversationRetryCell(props: TaskConversationRetryCellProps) {
  const { retry } = props;

  return (
    <div className='flex w-full gap-2 pt-2 pb-3 border-gray-200 overflow-hidden shrink-0'>
      <MessageAvatar imageUrl={undefined} username={WORKFLOW_AI_USERNAME} />
      <div className='flex-1 flex w-full flex-col gap-1 overflow-hidden font-lato'>
        <div className='w-full flex pt-[2px] gap-2 items-center justify-between'>
          <span className='font-semibold text-gray-900 text-[13px]'>{WORKFLOW_AI_USERNAME}</span>
        </div>
        <div className='flex flex-row gap-2 w-fit items-center'>
          <div className='flex-1 text-sm text-gray-500 whitespace-break-spaces'>Something went wrong.</div>
          <Button
            variant='newDesignGray'
            onClick={retry}
            size='sm'
            icon={<ArrowClockwise16Regular />}
            className='bg-gray-200/70 hover:bg-gray-300/70'
          >
            Try Again
          </Button>
        </div>
      </div>
    </div>
  );
}

type TaskConversationMessageProps = {
  message: ConversationMessage;
  showHeaderForAgent: boolean;
};

export function TaskConversationMessage(props: TaskConversationMessageProps) {
  const { message, showHeaderForAgent } = props;
  const { user } = useAuth();

  const isUserMessage = message.username !== WORKFLOW_AI_USERNAME && message.username !== undefined;

  if (isUserMessage) {
    return (
      <div className='flex py-2 justify-end overflow-hidden shrink-0'>
        <div className='flex max-w-[80%] rounded-[2px] bg-gray-100 p-2 text-gray-900 text-[13px] whitespace-pre-wrap'>
          {message.message}
        </div>
      </div>
    );
  }

  return (
    <div className='flex flex-col w-full gap-2 py-2 overflow-hidden shrink-0'>
      {showHeaderForAgent && (
        <div className='flex flex-row gap-2 w-full items-center'>
          <MessageAvatar imageUrl={message.imageUrl} username={message.username} />
          <div className='flex flex-row gap-1 justify-between flex-1 items-center'>
            <div className='font-semibold text-gray-900 text-[13px]'>{message.username}</div>
            {message.date && (
              <div className='text-[12px] text-center text-gray-500 font-normal'>{dayjs(message.date).fromNow()}</div>
            )}
          </div>
        </div>
      )}
      {typeof message.message === 'string' ? (
        <MarkdownMessageTextView message={message.message} />
      ) : (
        <div className='flex w-full text-[13px] text-gray-900 whitespace-pre-wrap'>{message.message}</div>
      )}
      {message.component}
      {message.feedbackToken && <FeedbackButtons feedbackToken={message.feedbackToken} userID={user?.id} />}
    </div>
  );
}
