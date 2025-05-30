import { cx } from 'class-variance-authority';
import { useCallback, useRef, useState } from 'react';
import { ImagePlaceholderIcon } from '@/components/icons/ImagePlaceholderIcon';
import { displayErrorToaster } from '@/components/ui/Sonner';
import { IMAGE_MIME_TYPES } from '@/lib/constants';
import { ReadonlyValue } from '../ReadOnlyValue';
import { ValueViewerProps } from '../utils';
import { DocumentPreviewControls } from './DocumentPreviewControls';
import { FileUploader } from './FileUploader';
import { URLFileUploader } from './URLFileUploader';
import { FileValueType, extractFileSrc } from './utils';

const ZOOM_FACTOR = 4;
const MIME_TYPES = IMAGE_MIME_TYPES.join(',');
const ALLOWED_EXTENSIONS = new Set(IMAGE_MIME_TYPES.map((type) => type.split('/')[1]));

type UniversalImageValueViewerProps = {
  value: FileValueType | undefined;
  className: string | undefined;
  editable: boolean | undefined;
  onEdit: ((keyPath: string, newVal: FileValueType | undefined, triggerSave?: boolean | undefined) => void) | undefined;
  keyPath: string;
  readonly?: boolean;
  hideCloseButton?: boolean;
  hideMagnification?: boolean;
};

export function UniversalImageValueViewer(props: UniversalImageValueViewerProps) {
  const {
    value,
    className,
    editable,
    onEdit,
    keyPath,
    readonly,
    hideCloseButton = false,
    hideMagnification = false,
  } = props;

  const [zoomPosition, setZoomPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const imgRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLDivElement, MouseEvent>) => {
    if (!imgRef.current) return;
    const { left, top, width, height } = imgRef.current.getBoundingClientRect();
    const x = ((event.pageX - left) / width) * 100;
    const y = ((event.pageY - top) / height) * 100;
    setZoomPosition({ x, y });
  }, []);

  const handleMouseLeave = useCallback(() => {
    setZoomPosition(null);
  }, []);

  const isRealImage = value && value?.content_type?.startsWith('image');

  const onChange = useCallback(
    async (file: File) => {
      const reader = new FileReader();
      reader.onload = () => {
        const data = reader.result as string;
        const newVal = {
          name: file.name,
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

  const onUrlLoad = useCallback(
    (url: string) => {
      const strippedUrl = url.split('?')[0];
      const fileType = strippedUrl.split('.').pop();
      if (!fileType || !ALLOWED_EXTENSIONS.has(fileType)) {
        displayErrorToaster('Invalid image type');
        return;
      }
      onEdit?.(keyPath, {
        name: strippedUrl.split('/').pop() || 'Image',
        content_type: `image/${fileType}`,
        url,
      });
    },
    [onEdit, keyPath]
  );

  const src = extractFileSrc(value);

  // If we don't have a file to show and we are not uploading it we show nothing
  if (!src && !editable) {
    return null;
  }

  if (!src) {
    return (
      <div className='w-full flex flex-col gap-3'>
        <FileUploader className={className} onChange={onChange} accept={MIME_TYPES} text='Any PNG, JPEG or WEBP' />
        <URLFileUploader onLoad={onUrlLoad} />
      </div>
    );
  }

  const alt = value?.name || 'Image';

  return (
    <div className='flex flex-col gap-1 relative'>
      <DocumentPreviewControls
        onEdit={onValueEdit}
        className={cx(className, '!p-0')}
        readonly={readonly || hideCloseButton}
        dialogContent={
          <div className='flex items-center justify-center overflow-hidden p-1'>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={src} alt={value?.name} className='h-full rounded-md shadow' />
          </div>
        }
      >
        <div
          className='flex items-center justify-center overflow-hidden'
          ref={imgRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} className='w-auto max-w-[250px] rounded-md shadow' />
        </div>
      </DocumentPreviewControls>
      {isRealImage && zoomPosition && !!imgRef.current && !hideMagnification && (
        <div
          className='rounded-md shadow z-[100] fixed'
          style={{
            backgroundImage: `url(${src})`,
            backgroundPosition: `${zoomPosition.x}% ${zoomPosition.y}%`,
            backgroundSize: `${ZOOM_FACTOR * 100}%`,
            height: Math.min(imgRef?.current?.clientHeight || 0, 200), // Added Math.min
            width: imgRef?.current?.clientWidth || 0,
            pointerEvents: 'none',
            top: imgRef.current.getBoundingClientRect().bottom + 8, // Also updated here
            left: imgRef.current.getBoundingClientRect().left,
          }}
        />
      )}
    </div>
  );
}

export function ImageValueViewer(props: ValueViewerProps<unknown>) {
  const { editable, showTypes, showTypesForFiles } = props;

  if (!editable && (showTypes || showTypesForFiles)) {
    return <ReadonlyValue {...props} value='image' referenceValue={undefined} icon={<ImagePlaceholderIcon />} />;
  }

  const castedValue = props.value as FileValueType | undefined;

  return (
    <UniversalImageValueViewer
      value={castedValue}
      className={props.className}
      editable={props.editable}
      onEdit={props.onEdit}
      keyPath={props.keyPath}
    />
  );
}
