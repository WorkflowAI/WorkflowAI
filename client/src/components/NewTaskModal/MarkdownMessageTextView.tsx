import { Copy16Regular } from '@fluentui/react-icons';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { prism } from 'react-syntax-highlighter/dist/esm/styles/prism';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { useCopyToClipboard } from 'usehooks-ts';
import { cn } from '@/lib/utils';
import { Button } from '../ui/Button';
import { displaySuccessToaster } from '../ui/Sonner';

type CodeBlockProps = {
  children: React.ReactNode;
};

function CodeBlock(props: CodeBlockProps) {
  const { children } = props;

  const [, copy] = useCopyToClipboard();

  // Extract the code content from the children
  let codeContent = '';
  let detectedLanguage = 'text';

  React.Children.forEach(children, (child) => {
    if (React.isValidElement(child)) {
      if (typeof child.props.children === 'string') {
        codeContent = child.props.children;
      }
      // Check if this is a code element with language class
      if (child.props.className && typeof child.props.className === 'string') {
        const langMatch = child.props.className.match(/language-(\w+)/);
        if (langMatch) {
          detectedLanguage = langMatch[1];
        }
      }
    }
  });

  const onCopy = useCallback(() => {
    copy(codeContent);
    displaySuccessToaster('Copied to clipboard');
  }, [copy, codeContent]);

  return (
    <div className='relative group flex w-full'>
      <SyntaxHighlighter
        language={detectedLanguage}
        style={prism}
        wrapLines={true}
        wrapLongLines={true}
        customStyle={{
          background: '#FFFFFF',
          fontSize: '12px',
          fontFamily: 'monospace',
          wordWrap: 'break-word',
          whiteSpace: 'pre-wrap',
        }}
        className='flex w-full rounded-[2px] border border-gray-200 p-4'
      >
        {codeContent}
      </SyntaxHighlighter>
      <Button
        variant='newDesignGray'
        icon={<Copy16Regular />}
        onClick={onCopy}
        className='absolute top-4 right-2 w-7 h-7 px-0 py-0 opacity-0 group-hover:opacity-100 transition-all delay-100'
      />
    </div>
  );
}

type MarkdownMessageTextViewProps = {
  message: string;
  className?: string;
};

export function MarkdownMessageTextView(props: MarkdownMessageTextViewProps) {
  const { message, className } = props;
  const [displayedMessage, setDisplayedMessage] = useState(message);
  const frameRef = useRef<number>();
  const previousMessageRef = useRef(message);
  const timeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (message === previousMessageRef.current) return;

    if (frameRef.current) cancelAnimationFrame(frameRef.current);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(() => {
      frameRef.current = requestAnimationFrame(() => {
        setDisplayedMessage(message);
        previousMessageRef.current = message;
      });
    }, 48);

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [message]);

  return (
    <div className='flex w-full h-max transition-all duration-150 ease-in-out opacity-100 scale-100'>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
        }}
        className={cn(
          'flex flex-col w-full text-[13px] prose prose-sm max-w-none [&>ul]:list-disc [&>ul]:pl-6 [&>ul]:space-y-4 [&>ul]:my-4 prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-800 prose-h1:text-base prose-h1:font-semibold prose-h1:mb-2 prose-h2:text-sm prose-h2:font-semibold prose-h2:mb-2 prose-h3:text-xs prose-h3:font-semibold prose-h3:mb-2 [&>table]:border-collapse [&>table]:w-full [&>table_th]:border [&>table_th]:border-gray-300 [&>table_th]:p-2 [&>table_th]:bg-gray-50 [&>table_td]:border [&>table_td]:border-gray-300 [&>table_td]:p-2 [&>details]:border [&>details]:border-gray-200 [&>details]:rounded-md [&>details]:p-2 [&>details_summary]:cursor-pointer [&>details_summary]:font-medium [&_kbd]:bg-gray-100 [&_kbd]:border [&_kbd]:border-gray-300 [&_kbd]:rounded [&_kbd]:px-1.5 [&_kbd]:py-0.5 [&_kbd]:text-xs [&_kbd]:font-semibold [&_code]:text-[12px]',
          className
        )}
      >
        {displayedMessage}
      </ReactMarkdown>
    </div>
  );
}
