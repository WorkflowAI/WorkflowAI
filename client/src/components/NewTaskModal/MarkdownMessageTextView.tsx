import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

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
    <div className={`transition-all duration-150 ease-in-out opacity-100 scale-100`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        className={cn(
          'w-full text-[13px] prose prose-sm max-w-none [&>ul]:list-disc [&>ul]:pl-6 [&>ul]:space-y-4 [&>ul]:my-4 prose-a:text-blue-600 prose-a:underline hover:prose-a:text-blue-800 prose-h1:text-base prose-h1:font-semibold prose-h1:mb-2 prose-h2:text-sm prose-h2:font-semibold prose-h2:mb-2 prose-h3:text-xs prose-h3:font-semibold prose-h3:mb-2 [&>table]:border-collapse [&>table]:w-full [&>table_th]:border [&>table_th]:border-gray-300 [&>table_th]:p-2 [&>table_th]:bg-gray-50 [&>table_td]:border [&>table_td]:border-gray-300 [&>table_td]:p-2 [&>details]:border [&>details]:border-gray-200 [&>details]:rounded-md [&>details]:p-2 [&>details_summary]:cursor-pointer [&>details_summary]:font-medium [&_kbd]:bg-gray-100 [&_kbd]:border [&_kbd]:border-gray-300 [&_kbd]:rounded [&_kbd]:px-1.5 [&_kbd]:py-0.5 [&_kbd]:text-xs [&_kbd]:font-semibold',
          className
        )}
      >
        {displayedMessage}
      </ReactMarkdown>
    </div>
  );
}
