import { DeviceEqFilled, DismissFilled, PauseRegular, PlayRegular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { displayErrorToaster } from '@/components/ui/Sonner';
import { hashFile } from '@/lib/hash';
import { FileInputRequest } from '@/types/workflowAI';
import { ReadonlyValue } from '../ReadOnlyValue';
import { ValueViewerProps } from '../utils';
import { FileUploader } from './FileUploader';
import { TranscriptionViewer } from './TranscriptionViewer';
import { FileValueType, extractFileSrc } from './utils';

// 60% of the loading time is spent on the browser
const BROWSER_LOADING_TIME_PERCENT = 0.6;
const BROWSER_PROGRESS_START = 0.05;
const BROWSER_ON_BROWSER_PROGRESS_START = 0.3;

function AudioWaveform() {
  const [barCount, setBarCount] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const heights = useMemo(() => {
    return Array.from({ length: 1000 }, () => Math.random() * 100);
  }, []);

  useEffect(() => {
    const updateBarCount = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.offsetWidth;
        const barWidth = 3;
        const newBarCount = Math.floor(containerWidth / barWidth);
        setBarCount(newBarCount);
      }
    };

    updateBarCount();
    window.addEventListener('resize', updateBarCount);
    return () => window.removeEventListener('resize', updateBarCount);
  }, []);

  return (
    <div ref={containerRef} className='flex-grow w-full h-9 overflow-hidden items-center justify-center'>
      {[...Array(barCount)].map((_, index) => (
        <div
          key={index}
          className='inline-block w-1 bg-slate-900 align-middle rounded-full'
          style={{
            height: `${heights[index % heights.length]}%`,
            marginRight: '2px',
          }}
        />
      ))}
    </div>
  );
}

type UniversalAudioValueViewerProps = {
  value: FileValueType | undefined;
  className: string | undefined;
  editable: boolean | undefined;
  onEdit: ((keyPath: string, newVal: FileValueType | undefined, triggerSave?: boolean | undefined) => void) | undefined;
  keyPath: string;
  transcriptions: Record<string, string> | undefined;
  fetchAudioTranscription: ((payload: FileInputRequest) => Promise<string | undefined>) | undefined;
  handleUploadFile:
    | ((
        formData: FormData,
        hash: string,
        onProgress?: ((progress: number) => void) | undefined
      ) => Promise<string | undefined>)
    | undefined;
  hideCloseButton?: boolean;
};

export function UniversalAudioValueViewer(props: UniversalAudioValueViewerProps) {
  const {
    value,
    className,
    editable,
    onEdit,
    keyPath,
    transcriptions,
    fetchAudioTranscription,
    handleUploadFile,
    hideCloseButton = false,
  } = props;

  const castedValue = value as FileValueType | undefined;
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const [textTranscription, setTextTranscription] = useState<string | undefined>(undefined);
  const [transcriptionLoading, setTranscriptionLoading] = useState(false);
  const lockTranscription = useRef(false);

  const updateTextTranscription = useCallback(
    async (data: string, contentType: string) => {
      if (!fetchAudioTranscription || lockTranscription.current) return;
      lockTranscription.current = true;
      setTranscriptionLoading(true);
      try {
        const transcription = await fetchAudioTranscription({
          file_id: hashFile(data),
          data,
          format: contentType.split('/')[1] as FileInputRequest['format'],
        });
        if (transcription) {
          setTextTranscription(transcription);
        }
      } catch (err) {
        console.error(err);
        setTextTranscription('Transcription Unavailable');
      } finally {
        setTranscriptionLoading(false);
        lockTranscription.current = false;
      }
    },
    [fetchAudioTranscription]
  );

  const [uploadProps, setUploadProps] = useState<
    | {
        progress?: number;
        fileName?: string;
      }
    | undefined
  >(undefined);
  const setUploadBrowserProgress = useCallback(
    (progress: number) => {
      setUploadProps((prev) => ({
        ...prev,
        progress: Math.max(progress * BROWSER_LOADING_TIME_PERCENT, BROWSER_ON_BROWSER_PROGRESS_START),
      }));
    },
    [setUploadProps]
  );
  const setUploadServerProgress = useCallback(
    (progress: number) => {
      setUploadProps((prev) => ({
        ...prev,
        progress: BROWSER_LOADING_TIME_PERCENT + progress * (1 - BROWSER_LOADING_TIME_PERCENT),
      }));
    },
    [setUploadProps]
  );
  const setUploadFileName = useCallback(
    (fileName?: string) => {
      setUploadProps({ fileName, progress: BROWSER_PROGRESS_START });
    },
    [setUploadProps]
  );
  const resetUploadProps = useCallback(() => {
    setUploadProps(undefined);
  }, [setUploadProps]);

  const onChange = useCallback(
    async (file: File) => {
      if (!handleUploadFile) return;
      setUploadFileName(file.name);
      const reader = new FileReader();

      reader.onprogress = (event) => {
        if (event.lengthComputable) {
          const precentRead = Math.round(event.loaded / event.total);
          setUploadBrowserProgress(precentRead);
        }
      };
      reader.onload = async () => {
        const rawData = reader.result as string;
        const data = rawData.split(',')[1];
        const contentType = file.type;
        // TODO: Update this once we have a way to fetch the transcriptions based on the storage_url
        updateTextTranscription(data, contentType);
        const hash = hashFile(data);
        const formData = new FormData();
        formData.append('file', file);
        try {
          const storage_url = await handleUploadFile(formData, hash, setUploadServerProgress);
          if (!storage_url) {
            throw new Error('Failed to upload file');
          }
          const newVal = {
            content_type: contentType,
            url: storage_url,
          };
          onEdit?.(keyPath, newVal);
          setIsPlaying(false);
        } catch (error) {
          console.error(error);
          displayErrorToaster('Failed to upload file');
        } finally {
          resetUploadProps();
        }
      };
      reader.readAsDataURL(file);
    },
    [
      keyPath,
      onEdit,
      resetUploadProps,
      setUploadBrowserProgress,
      setUploadFileName,
      setUploadServerProgress,
      updateTextTranscription,
      handleUploadFile,
    ]
  );

  const handlePlayPause = useCallback(() => {
    if (audioRef.current) {
      if (audioRef.current.paused) {
        audioRef.current
          .play()
          .then(() => setIsPlaying(true))
          .catch(console.error);
      } else {
        audioRef.current.pause();
        setIsPlaying(false);
      }
    }
  }, []);

  const handleDismiss = useCallback(() => {
    onEdit?.(keyPath, undefined);
    setIsPlaying(false);
  }, [onEdit, keyPath]);

  useEffect(() => {
    const audioElement = audioRef.current;
    if (audioElement) {
      const handlePlay = () => setIsPlaying(true);
      const handlePause = () => setIsPlaying(false);
      const handleEnded = () => setIsPlaying(false);

      audioElement.addEventListener('play', handlePlay);
      audioElement.addEventListener('pause', handlePause);
      audioElement.addEventListener('ended', handleEnded);

      return () => {
        audioElement.removeEventListener('play', handlePlay);
        audioElement.removeEventListener('pause', handlePause);
        audioElement.removeEventListener('ended', handleEnded);
      };
    }
  }, [castedValue]);

  const runTranscription = useMemo(() => {
    return transcriptions?.[keyPath];
  }, [transcriptions, keyPath]);

  const transcription = textTranscription || runTranscription;

  const src = extractFileSrc(castedValue);

  if (!src && !editable) {
    return null;
  }

  if (!castedValue || !src) {
    return (
      <FileUploader
        className={className}
        onChange={onChange}
        accept='audio/wav,audio/mp3,audio/aiff,audio/aac,audio/ogg,audio/flac,audio/mpeg'
        text='Any MP3, WAV, AIFF, AAC, OGG Vorbis or FLAC'
        uploadProps={uploadProps}
      />
    );
  }

  return (
    <div
      className={cx(
        'flex flex-col gap-4 w-full bg-gray-50 rounded-[2px] px-3 py-5 border border-gray-200 border-dashed font-lato',
        className
      )}
    >
      <audio ref={audioRef} src={src} />
      <div className='flex flex-row gap-3 items-center justify-between'>
        <Button
          variant='outline'
          size='icon'
          fluentIcon={isPlaying ? PauseRegular : PlayRegular}
          onClick={handlePlayPause}
          className='shrink-0'
        />
        <AudioWaveform />
        {editable && !hideCloseButton && (
          <Button
            variant='newDesign'
            size='icon'
            fluentIcon={DismissFilled}
            onClick={handleDismiss}
            className='shrink-0'
          />
        )}
      </div>
      <TranscriptionViewer transcription={transcription} transcriptionLoading={transcriptionLoading} />
    </div>
  );
}

export function AudioValueViewer(props: ValueViewerProps<FileValueType | undefined>) {
  const { editable, showTypes, showTypesForFiles } = props;

  if (!editable && (showTypes || showTypesForFiles)) {
    return <ReadonlyValue {...props} value='audio' referenceValue={undefined} icon={<DeviceEqFilled />} />;
  }

  const castedValue = props.value as FileValueType | undefined;

  return (
    <UniversalAudioValueViewer
      value={castedValue}
      className={props.className}
      editable={props.editable}
      onEdit={props.onEdit}
      keyPath={props.keyPath}
      transcriptions={props.transcriptions}
      fetchAudioTranscription={props.fetchAudioTranscription}
      handleUploadFile={props.handleUploadFile}
    />
  );
}
