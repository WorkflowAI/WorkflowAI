import { Copy16Regular, Dismiss12Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import SyntaxHighlighter from 'react-syntax-highlighter';
import { xcode } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { Loader } from '@/components/ui/Loader';
import { formatFractionalCurrency } from '@/lib/formatters/numberFormatters';
import { useCopy } from '@/lib/hooks/useCopy';
import { LLMCompletionTypedMessages } from '@/types/workflowAI';
import { MessagePreparedForDisplay, prepareMessageForDisplay, processResponse } from './utils';

type CodeProps = {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
};

function CodeBlock(props: { language: string; value: string }) {
  const { language, value } = props;
  return (
    <SyntaxHighlighter style={xcode} language={language} className='border border-gray-200 p-2 my-2'>
      {value}
    </SyntaxHighlighter>
  );
}

const MARKDOWN_COMPONENTS = {
  code({ inline, className, children, ...props }: CodeProps) {
    const match = /language-(\w+)/.exec(className || '');
    if (!inline && match) {
      return <CodeBlock language={match[1]} value={String(children).replace(/\n$/, '')} />;
    } else {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
  },
  img: ({ src }: React.ImgHTMLAttributes<HTMLImageElement>) => <div>{`<img src='${src}'/>`}</div>,
  a: ({ children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <span {...props}>{children}</span>,
};

type PromptEntryProps = {
  title: string;
  text: string;
  orginalText: string;
};

function PromptEntry(props: PromptEntryProps) {
  const { title, text, orginalText } = props;
  const copy = useCopy();
  const onCopy = useCallback(() => {
    copy(orginalText);
  }, [orginalText, copy]);

  return (
    <div className='flex flex-col w-full max-h-[420px] border border-gray-200 rounded-[2px] bg-gradient-to-b from-white/90 to-white/0'>
      <div className='flex justify-between items-center text-gray-700 w-full px-4 border-b border-gray-200 border-dashed'>
        <div className='text-gray-700 text-[14px] font-semibold py-3'>{title}</div>
        <Button
          variant='newDesign'
          icon={<Copy16Regular className='w-[18px] h-[18px]' />}
          onClick={onCopy}
          className='w-8 h-8 px-0 py-0'
        />
      </div>
      <div className='px-4 py-3 text-gray-900 text-[13px] overflow-auto'>
        <ReactMarkdown components={MARKDOWN_COMPONENTS}>{text}</ReactMarkdown>
      </div>
    </div>
  );
}

type CompletionEntryProps = {
  key: string;
  index: number;
  indexToShow: number;
  completion: LLMCompletionTypedMessages;
  selected: boolean;
  onSelect: (index: number) => void;
};

function CompletionEntry(props: CompletionEntryProps) {
  const { key, index, indexToShow, completion, selected, onSelect } = props;
  const cost = formatFractionalCurrency(completion.usage.completion_cost_usd) ?? '-';

  const [isHovering, setIsHovering] = useState(false);

  return (
    <div
      key={key}
      className={cx(
        'flex flex-col w-full p-2 hover:bg-indigo-50/50 cursor-pointer',
        selected && 'bg-indigo-50 border-l-2 border-indigo-700'
      )}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
      onClick={() => onSelect(index)}
    >
      <div className={cx('text-[13px] font-semibold', isHovering || selected ? 'text-indigo-700' : 'text-gray-700')}>
        {`Completion #${indexToShow + 1}`}
      </div>
      <div className={cx('text-[13px]', isHovering || selected ? 'text-indigo-700' : 'text-gray-500')}>{cost}</div>
    </div>
  );
}

type PromptDialogContentProps = {
  isInitialized: boolean;
  llmCompletions: LLMCompletionTypedMessages[] | undefined;
  selectedCompletion: LLMCompletionTypedMessages | undefined;
  selectedCompletionIndex: number;
  setSelectedCompletionIndex: (index: number) => void;
  messagesPreparedForDisplay: MessagePreparedForDisplay[];
  processedResponse: string | null | undefined;
};

function PromptDialogContent(props: PromptDialogContentProps) {
  const {
    isInitialized,
    llmCompletions,
    selectedCompletion,
    selectedCompletionIndex,
    setSelectedCompletionIndex,
    messagesPreparedForDisplay,
    processedResponse,
  } = props;

  if (!isInitialized) {
    return <Loader centered />;
  }

  return (
    <div className='flex flex-row flex-1 overflow-hidden w-full'>
      {!!llmCompletions && llmCompletions.length > 1 && (
        <div className='flex flex-col w-[200px] border-r border-gray-200 border-dashed p-3 overflow-y-auto'>
          {llmCompletions.map((completion, index) => (
            <CompletionEntry
              key={index.toString()}
              index={index}
              indexToShow={llmCompletions.length - index - 1}
              completion={completion}
              selected={selectedCompletionIndex === index}
              onSelect={setSelectedCompletionIndex}
            />
          ))}
        </div>
      )}
      <div className='flex flex-col flex-1 gap-4 items-top overflow-y-auto py-3 px-4'>
        {messagesPreparedForDisplay.map((message, index) => (
          <PromptEntry key={index} title={message.title} text={message.text} orginalText={message.orginalText} />
        ))}
        {!!selectedCompletion?.response && (
          <PromptEntry
            title='RAW COMPLETION'
            text={processedResponse ?? selectedCompletion.response}
            orginalText={selectedCompletion.response}
          />
        )}
      </div>
    </div>
  );
}

type PromptDialogProps = {
  open: boolean;
  onOpenChange: () => void;
  completions: LLMCompletionTypedMessages[];
};

export function PromptDialog(props: PromptDialogProps) {
  const { open, onOpenChange, completions } = props;

  const llmCompletions = useMemo(() => {
    if (!completions || !completions.length) {
      return undefined;
    }
    return [...completions].reverse();
  }, [completions]);

  const [selectedCompletionIndex, setSelectedCompletionIndex] = useState<number>(0);

  useEffect(() => {
    if (open) {
      setSelectedCompletionIndex(0);
    }
  }, [open]);

  const selectedCompletion = useMemo(() => {
    return llmCompletions?.[selectedCompletionIndex];
  }, [llmCompletions, selectedCompletionIndex]);

  const messagesPreparedForDisplay: MessagePreparedForDisplay[] = useMemo(() => {
    const messages = selectedCompletion?.messages ?? [];
    return messages.map((message: Record<string, unknown>) => prepareMessageForDisplay(message));
  }, [selectedCompletion]);

  const processedResponse = useMemo(() => {
    if (!selectedCompletion) {
      return null;
    }
    return processResponse(selectedCompletion.response);
  }, [selectedCompletion]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='w-[1100px] max-w-[90vw] max-h-[90vh] h-[900px] p-0 overflow-hidden flex flex-col bg-custom-gradient-1'>
        <div className='flex flex-col w-full h-full overflow-hidden'>
          <div className='flex gap-2 items-center w-full whitespace-nowrap border-b border-gray-200 border-dashed py-3 px-4'>
            <Button
              onClick={onOpenChange}
              variant='newDesign'
              icon={<Dismiss12Regular className='w-3 h-3' />}
              className='w-7 h-7'
              size='none'
            />
            <h1 className='text-gray-900 text-[16px] font-semibold px-2'>Prompt details</h1>
          </div>
          <PromptDialogContent
            isInitialized={true}
            llmCompletions={llmCompletions}
            selectedCompletion={selectedCompletion}
            selectedCompletionIndex={selectedCompletionIndex}
            setSelectedCompletionIndex={setSelectedCompletionIndex}
            messagesPreparedForDisplay={messagesPreparedForDisplay}
            processedResponse={processedResponse}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
