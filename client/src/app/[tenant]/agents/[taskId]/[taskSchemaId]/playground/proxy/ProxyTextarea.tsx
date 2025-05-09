import { useCallback, useMemo } from 'react';
import { Textarea } from '@/components/ui/Textarea';
import { ProxyMessageContent, createEmptyMessageContent, formatResponseToText } from './utils';

type ProxyTextareaProps = {
  content: ProxyMessageContent | undefined;
  setContent: (content: ProxyMessageContent) => void;
  placeholder: string;
  minHeight?: number;
};

export function ProxyTextarea(props: ProxyTextareaProps) {
  const { content, placeholder, minHeight, setContent } = props;

  const onChange = useCallback(
    (value: string) => {
      let newContent = content ?? createEmptyMessageContent();
      newContent = { ...newContent, text: value };
      setContent(newContent);
    },
    [content, setContent]
  );

  const text = useMemo(() => {
    return formatResponseToText(content?.text);
  }, [content]);

  return (
    <Textarea
      className='flex text-gray-900 placeholder:text-gray-500 font-normal text-[13px] rounded-[2px] border-gray-300 overflow-y-auto focus-within:ring-inset'
      style={{ minHeight: minHeight }}
      placeholder={placeholder}
      value={text}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
