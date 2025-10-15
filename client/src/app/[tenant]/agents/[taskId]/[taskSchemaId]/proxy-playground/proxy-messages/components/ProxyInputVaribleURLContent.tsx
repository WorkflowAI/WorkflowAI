import { useCallback, useMemo } from 'react';
import { ProxyMessageContent } from '@/types/workflowAI';
import { formatResponseToText } from '../utils';
import { VariablesTextarea } from '../variables-textarea/VariablesTextarea';

function containsInputVaribleOnly(text: string | undefined): boolean {
  if (!text) {
    return false;
  }
  // Only return true if the text is exactly {{something}}, with nothing else before or after
  return /^\{\{[^{}]+\}\}$/.test(text.trim());
}

type Props = {
  content: ProxyMessageContent | undefined;
  setContent: (content: ProxyMessageContent) => void;
  readOnly?: boolean;
  inputVariblesKeys?: string[];
  supportInputVaribles?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
};

export function ProxyInputVaribleURLContent(props: Props) {
  const { content, setContent, readOnly, inputVariblesKeys, supportInputVaribles = true, onFocus, onBlur } = props;

  const onChange = useCallback(
    (value: string) => {
      let newFile = content?.file ?? {};
      newFile = { ...newFile, url: value };
      setContent({ ...content, file: newFile });
    },
    [content, setContent]
  );

  const text = useMemo(() => {
    return formatResponseToText(content?.file?.url);
  }, [content]);

  const format = useMemo(() => {
    if (
      content?.file !== undefined &&
      'format' in content.file &&
      content.file.format !== undefined &&
      typeof content.file.format === 'string'
    ) {
      return content.file.format;
    }
    return undefined;
  }, [content]);

  const wrongText = useMemo(() => {
    const url = content?.file?.url;
    if (url === undefined) {
      return true;
    }
    return !containsInputVaribleOnly(url);
  }, [content]);

  return (
    <div className='flex flex-col w-full gap-1.5'>
      <div className='flex flex-col w-full relative'>
        <VariablesTextarea
          text={text ?? ''}
          onTextChange={onChange}
          placeholder={undefined}
          readOnly={readOnly}
          inputVariblesKeys={inputVariblesKeys}
          supportInputVaribles={supportInputVaribles}
          onFocus={onFocus}
          onBlur={onBlur}
        />
        {wrongText && (
          <div className='absolute top-[-52px] left-[-12px] text-[13px] text-white px-1.5 py-0.5 bg-gray-700 rounded-[2px] shadow-md'>
            Content is type: {format}; additional text cannot be added
          </div>
        )}
      </div>
    </div>
  );
}
