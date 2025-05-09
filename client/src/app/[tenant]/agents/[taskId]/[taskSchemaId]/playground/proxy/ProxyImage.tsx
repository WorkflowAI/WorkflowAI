import { useCallback } from 'react';
import { UniversalImageValueViewer } from '@/components/ObjectViewer/FileViewers/ImageValueViewer';
import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';

type Props = {
  file: FileValueType;
  setFile: (file: FileValueType | undefined) => void;
};

export function ProxyImage(props: Props) {
  const { file, setFile } = props;

  const onEdit = useCallback(
    (keyPath: string, newVal: FileValueType | undefined) => {
      if (!newVal) {
        const emptyFile: FileValueType = {
          content_type: file.content_type,
          data: undefined,
          storage_url: undefined,
          url: undefined,
        };
        setFile(emptyFile);
      } else {
        setFile(newVal);
      }
    },
    [setFile, file.content_type]
  );

  return <UniversalImageValueViewer value={file} className={undefined} editable={true} onEdit={onEdit} keyPath={'.'} />;
}
