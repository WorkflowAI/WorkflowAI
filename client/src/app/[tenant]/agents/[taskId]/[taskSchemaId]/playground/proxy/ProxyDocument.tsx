import { useCallback } from 'react';
import { UniversalDocumentValueViewer } from '@/components/ObjectViewer/FileViewers/DocumentValueViewer';
import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';

type Props = {
  file: FileValueType;
  setFile: (file: FileValueType | undefined) => void;
};

export function ProxyDocument(props: Props) {
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

  return (
    <UniversalDocumentValueViewer value={file} className={undefined} editable={true} onEdit={onEdit} keyPath={'.'} />
  );
}
