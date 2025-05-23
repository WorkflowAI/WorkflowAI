import { DocumentBulletList16Regular } from '@fluentui/react-icons';
import { cx } from 'class-variance-authority';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { DOCUMENT_MIME_TYPES, IMAGE_MIME_TYPES } from '@/lib/constants';
import { ReadonlyValue } from '../ReadOnlyValue';
import { ValueViewerProps } from '../utils';
import { CSVDocumentViewer } from './CSVDocumentViewer';
import { DocumentPreviewControls } from './DocumentPreviewControls';
import { FileUploader } from './FileUploader';
import { UniversalImageValueViewer } from './ImageValueViewer';
import { FileValueType, extractFileSrc } from './utils';

type TextDocumentViewerProps = {
  text: string;
  className?: string;
  isCSV: boolean;
};

function TextDocumentViewer(props: TextDocumentViewerProps) {
  const { text, className, isCSV } = props;
  return (
    <>
      {isCSV ? (
        <CSVDocumentViewer decodedText={text} className={className} />
      ) : (
        <div className={cx('rounded-md border p-1 whitespace-pre-line text-sm overflow-y-auto', className)}>{text}</div>
      )}
    </>
  );
}

type TextDocumentStorageViewerProps = {
  storageUrl: string;
  className?: string;
  isCSV: boolean;
};

const MIME_TYPES = [...DOCUMENT_MIME_TYPES, ...IMAGE_MIME_TYPES].join(',');

function TextDocumentStorageViewer(props: TextDocumentStorageViewerProps) {
  const { storageUrl, className, isCSV } = props;
  const [text, setText] = useState<string | null>(null);

  useEffect(() => {
    fetch(storageUrl)
      .then((res) => res.text())
      .then(setText);
  }, [storageUrl]);

  if (!text) return null;

  return <TextDocumentViewer text={text} className={className} isCSV={isCSV} />;
}

type TextDocumentBase64ViewerProps = {
  data: string | undefined;
  className?: string;
  isCSV: boolean;
};

function TextDocumentBase64Viewer(props: TextDocumentBase64ViewerProps) {
  const { data, className, isCSV } = props;

  const decodedText = useMemo(() => {
    if (!data) return null;
    try {
      return atob(data);
    } catch (error) {
      console.error('Error decoding base64 data:', error);
      return null;
    }
  }, [data]);

  if (!decodedText) return null;

  return <TextDocumentViewer text={decodedText} className={className} isCSV={isCSV} />;
}

type TextDocumentViewerWrapperProps = {
  value: FileValueType;
  className?: string;
};

function TextDocumentViewerWrapper(props: TextDocumentViewerWrapperProps) {
  const { value, className } = props;
  const { data, content_type, storage_url } = value;
  const isCSV = content_type?.includes('csv') ?? false;

  return storage_url ? (
    <TextDocumentStorageViewer storageUrl={storage_url} className={className} isCSV={isCSV} />
  ) : (
    <TextDocumentBase64Viewer data={data} className={className} isCSV={isCSV} />
  );
}

type UniversalDocumentValueViewerProps = {
  value: FileValueType | undefined;
  className: string | undefined;
  editable: boolean | undefined;
  onEdit: ((keyPath: string, newVal: FileValueType | undefined, triggerSave?: boolean | undefined) => void) | undefined;
  keyPath: string;
  readonly?: boolean;
  hideCloseButton?: boolean;
};

export function UniversalDocumentValueViewer(props: UniversalDocumentValueViewerProps) {
  const { value, className, editable, onEdit, keyPath, readonly, hideCloseButton } = props;
  const castedValue = value as FileValueType | undefined;

  const onChange = useCallback(
    async (file: File) => {
      const reader = new FileReader();
      reader.onload = () => {
        const data = reader.result as string;
        const newVal = {
          content_type: file.type,
          data: data.split(',')[1],
        };
        onEdit?.(keyPath, newVal);
      };
      reader.readAsDataURL(file);
    },
    [onEdit, keyPath]
  );

  const onValueEdit = useCallback(
    (newValue: FileValueType | undefined) => {
      onEdit?.(keyPath, newValue);
    },
    [onEdit, keyPath]
  );

  const src = extractFileSrc(castedValue);

  // If we don't have a file to show and we are not uploading it we show nothing
  if (!src && !editable) {
    return null;
  }

  if (!castedValue || !src) {
    return (
      <FileUploader
        className={className}
        onChange={onChange}
        accept={MIME_TYPES}
        text='Any PDF, CSV, TXT, PNG, JPEG or WEBP'
      />
    );
  }

  const isPdf = castedValue?.content_type?.includes('pdf') ?? false;
  const isImage = castedValue?.content_type?.includes('image') ?? false;

  if (isPdf) {
    return (
      <DocumentPreviewControls onEdit={onValueEdit} className={className} readonly={readonly || hideCloseButton}>
        <iframe className='w-full h-full rounded-md border' src={src} />
      </DocumentPreviewControls>
    );
  }
  if (isImage) {
    return <UniversalImageValueViewer {...props} />;
  }

  return (
    <DocumentPreviewControls
      onEdit={onValueEdit}
      className={className}
      readonly={readonly}
      dialogContent={<TextDocumentViewerWrapper value={castedValue} className='overflow-auto' />}
    >
      <TextDocumentViewerWrapper value={castedValue} className='max-h-[250px] max-w-[500px] overflow-hidden' />
    </DocumentPreviewControls>
  );
}

export function DocumentValueViewer(props: ValueViewerProps<unknown>) {
  const { editable, showTypes, showTypesForFiles } = props;

  if (!editable && (showTypes || showTypesForFiles)) {
    return (
      <ReadonlyValue {...props} value='document' referenceValue={undefined} icon={<DocumentBulletList16Regular />} />
    );
  }

  const castedValue = props.value as FileValueType | undefined;

  return (
    <UniversalDocumentValueViewer
      value={castedValue}
      className={props.className}
      editable={props.editable}
      onEdit={props.onEdit}
      keyPath={props.keyPath}
    />
  );
}
