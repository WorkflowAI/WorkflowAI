import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';
import { TaskOutputViewer } from '@/components/ObjectViewer/TaskOutputViewer';
import { FeaturePreview } from '@/store/features';
import { JsonSchema } from '@/types';
import { PlaceholderRectangle } from './PlaceholderRectangle';

type SuggestedFeaturesThumbnailProps = {
  preview: FeaturePreview | undefined;
  isStreaming: boolean;
};

export function SuggestedFeaturesThumbnail(props: SuggestedFeaturesThumbnailProps) {
  const { preview, isStreaming } = props;
  const outputSchema = preview?.output_schema_preview as JsonSchema;
  const previewOutput = preview?.output_preview;

  const shouldTruncate = useMemo(() => {
    if (!outputSchema) {
      return false;
    }
    if (outputSchema.type === 'object' && outputSchema.properties) {
      return Object.keys(outputSchema.properties).length > 1;
    }
    return false;
  }, [outputSchema]);

  return (
    <div className='flex w-full h-full px-10 py-8 justify-center overflow-clip border border-gray-100 rounded-[4px]'>
      <div className='flex w-full h-fit max-h-full bg-white rounded-[2px] p-4 shadow-md overflow-hidden'>
        {previewOutput ? (
          <div className='flex flex-col w-full h-full opacity-60 relative overflow-hidden'>
            <TaskOutputViewer
              value={previewOutput}
              noOverflow
              schema={outputSchema}
              defs={outputSchema?.$defs}
              className='w-full flex-1 overflow-y-auto overflow-x-hidden'
              errorsByKeypath={undefined}
              hideCopyValue={true}
              showTypesForFiles={true}
              supportTextWrapping={shouldTruncate}
            />
            {isStreaming && (
              <div className='absolute top-0 right-0'>
                <Loader2 className='w-4 h-4 animate-spin text-gray-400' />
              </div>
            )}
          </div>
        ) : (
          <div className='flex flex-col gap-3 w-full'>
            <PlaceholderRectangle className='w-[20%] h-[16px] animate-pulse' />
            <PlaceholderRectangle className='w-[40%] h-[16px] animate-pulse' />
            <PlaceholderRectangle className='w-[40%] h-[16px] animate-pulse' />
            <PlaceholderRectangle className='w-[70%] h-[16px] animate-pulse' />
          </div>
        )}
      </div>
    </div>
  );
}
