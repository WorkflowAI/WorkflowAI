import { useCallback, useMemo } from 'react';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { ProxyMessageContent } from '@/types/workflowAI';
import { createEmptyMessageContent, formatResponseToText } from '../utils';
import { VariablesTextarea } from '../variables-textarea/VariablesTextarea';

type ProxyTextareaProps = {
  content: ProxyMessageContent | undefined;
  setContent: (content: ProxyMessageContent) => void;
  placeholder: string;
  minHeight?: number;
  readOnly?: boolean;
  inputVariblesKeys?: string[];
  supportInputVaribles?: boolean;
  supportObjectViewerIfPossible?: boolean;
};

export function ProxyTextarea(props: ProxyTextareaProps) {
  const {
    content,
    placeholder,
    setContent,
    readOnly,
    inputVariblesKeys,
    supportInputVaribles = true,
    supportObjectViewerIfPossible = false,
  } = props;

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

  if (readOnly && supportObjectViewerIfPossible && !!content?.text) {
    try {
      const output = JSON.parse(content.text);
      if (!!output) {
        return (
          <TaskOutputViewer
            schema={undefined}
            value={output}
            referenceValue={undefined}
            defs={undefined}
            textColor='text-gray-900'
            className='flex sm:flex-1 w-full border border-gray-200 rounded-[2px] bg-white h-max mx-3 mt-1'
            showTypes={false}
            showDescriptionExamples={undefined}
            showDescriptionPopover={false}
            defaultOpenForSteps={false}
          />
        );
      }
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <VariablesTextarea
      text={text ?? ''}
      onTextChange={onChange}
      placeholder={placeholder}
      readOnly={readOnly}
      inputVariblesKeys={inputVariblesKeys}
      supportInputVaribles={supportInputVaribles}
    />
  );
}
