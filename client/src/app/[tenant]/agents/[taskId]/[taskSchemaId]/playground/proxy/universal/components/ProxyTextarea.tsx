import { useCallback, useMemo } from 'react';
import { Textarea } from '@/components/ui/Textarea';
import { ProxyMessageContent } from '@/types/workflowAI';
import { createEmptyMessageContent, formatResponseToText } from '../../utils';

type ProxyTextareaProps = {
  content: ProxyMessageContent | undefined;
  setContent: (content: ProxyMessageContent) => void;
  placeholder: string;
  minHeight?: number;
  readOnly?: boolean;
};

export function ProxyTextarea(props: ProxyTextareaProps) {
  const { content, placeholder, minHeight, setContent, readOnly } = props;

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
      className='flex py-0 text-gray-900 placeholder:text-gray-500 font-normal text-[13px] overflow-y-auto border-none focus:ring-0 !ring-0 outline-none focus:outline-none'
      style={{ minHeight: minHeight }}
      placeholder={placeholder}
      value={text}
      onChange={(e) => onChange(e.target.value)}
      readOnly={readOnly}
    />
  );
}
