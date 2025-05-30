import { useCallback } from 'react';
import { UniversalAudioValueViewer } from '@/components/ObjectViewer/FileViewers/AudioValueViewer';
import { FileValueType } from '@/components/ObjectViewer/FileViewers/utils';
import { useTaskParams } from '@/lib/hooks/useTaskParams';
import { useAudioTranscriptions } from '@/store/audio_transcriptions';
import { useUpload } from '@/store/upload';

type Props = {
  file: FileValueType;
  setFile: (file: FileValueType | undefined) => void;
  readonly?: boolean;
};

export function ProxyAudio(props: Props) {
  const { file, setFile, readonly } = props;

  const { tenant, taskId } = useTaskParams();

  const fetchAudioTranscription = useAudioTranscriptions((state) => state.fetchAudioTranscription);
  const { getUploadURL } = useUpload();

  const handleUploadFile = useCallback(
    async (formData: FormData, hash: string, onProgress?: (progress: number) => void) => {
      if (!tenant || !taskId) return undefined;
      return getUploadURL({
        tenant,
        taskId,
        form: formData,
        hash,
        onProgress,
      });
    },
    [getUploadURL, tenant, taskId]
  );

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
    <UniversalAudioValueViewer
      value={file}
      className={undefined}
      editable={!readonly}
      onEdit={onEdit}
      keyPath={'.'}
      transcriptions={undefined}
      fetchAudioTranscription={fetchAudioTranscription}
      handleUploadFile={handleUploadFile}
      hideCloseButton={true}
    />
  );
}
