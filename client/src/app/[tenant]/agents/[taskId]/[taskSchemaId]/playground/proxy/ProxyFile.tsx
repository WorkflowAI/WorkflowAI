import { useCallback } from 'react';
import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';
import { ProxyMessageContent } from '@/types/workflowAI';
import { ProxyAudio } from './ProxyAudio';
import { ProxyDocument } from './ProxyDocument';
import { ProxyImage } from './ProxyImage';

type Props = {
  content: ProxyMessageContent;
  setContent: (content: ProxyMessageContent) => void;
  readonly?: boolean;
};

export function ProxyFile(props: Props) {
  const { content, setContent, readonly } = props;

  const updateFile = useCallback(
    (file: FileValueType | undefined) => {
      setContent({ ...content, file });
    },
    [content, setContent]
  );

  if (!content.file) {
    return <div>No file</div>;
  }

  if (!content.file.content_type) {
    return <div>No content type</div>;
  }

  if (content.file.content_type.startsWith('image/')) {
    return <ProxyImage file={content.file} setFile={updateFile} readonly={readonly} />;
  }

  if (content.file.content_type.startsWith('audio/')) {
    return <ProxyAudio file={content.file} setFile={updateFile} readonly={readonly} />;
  }

  return <ProxyDocument file={content.file} setFile={updateFile} readonly={readonly} />;
}
