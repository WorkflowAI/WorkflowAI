import { useCallback, useMemo } from 'react';
import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';
import { ProxyMessageContent } from '@/types/workflowAI';
import { ProxyAudio } from './ProxyAudio';
import { ProxyDocument } from './ProxyDocument';
import { ProxyImage } from './ProxyImage';
import { ProxyRemovableContent } from './ProxyRemovableContent';

type Props = {
  content: ProxyMessageContent;
  setContent: (content: ProxyMessageContent) => void;
  readonly?: boolean;
  onRemoveContentEntry: () => void;
};

export function ProxyFile(props: Props) {
  const { content, setContent, readonly, onRemoveContentEntry } = props;

  const updateFile = useCallback(
    (file: FileValueType | undefined) => {
      setContent({ ...content, file });
    },
    [content, setContent]
  );

  const className = useMemo(() => {
    if ((!!content.file?.data || !!content.file?.url) && !content.file?.content_type?.startsWith('audio/')) {
      return undefined;
    }
    return 'w-full';
  }, [content.file]);

  if (!content.file) {
    return <div>No file</div>;
  }

  if (!content.file.content_type) {
    return <div>No content type</div>;
  }

  if (content.file.content_type.startsWith('image/')) {
    return (
      <ProxyRemovableContent isRemovable={!readonly} onRemove={onRemoveContentEntry} className={className}>
        <ProxyImage file={content.file} setFile={updateFile} readonly={readonly} />
      </ProxyRemovableContent>
    );
  }

  if (content.file.content_type.startsWith('audio/')) {
    return (
      <ProxyRemovableContent isRemovable={!readonly} onRemove={onRemoveContentEntry} className={className}>
        <ProxyAudio file={content.file} setFile={updateFile} readonly={readonly} />
      </ProxyRemovableContent>
    );
  }

  return (
    <ProxyRemovableContent isRemovable={!readonly} onRemove={onRemoveContentEntry} className={className}>
      <ProxyDocument file={content.file} setFile={updateFile} readonly={readonly} />
    </ProxyRemovableContent>
  );
}
