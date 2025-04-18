import Image from 'next/image';
import { cn } from '@/lib/utils';
import { ModelResponse, VersionV1 } from '@/types/workflowAI';

type ModelBadgeProps = {
  version?: VersionV1;
  model?: ModelResponse;
  className?: string;
};

export function ModelBadge(props: ModelBadgeProps) {
  const { version, model, className } = props;

  const modelIconURL = model?.icon_url ?? (version?.properties?.model_icon as string | undefined);
  const modelName = model?.name ?? version?.model;

  return (
    <div className={cn('flex h-full flex-row gap-2 overflow-hidden items-center', className)}>
      {!!modelIconURL && (
        <div className='flex items-center justify-center w-6 h-6 bg-white border border-gray-200 rounded-[2px] shrink-0'>
          <Image src={modelIconURL} alt='' width={14} height={14} className='w-[14px] h-[14px] shrink-0' />
        </div>
      )}
      <div className='truncate whitespace-nowrap text-ellipsis overflow-hidden text-[13px] font-normal text-gray-700 min-w-0'>
        {modelName}
      </div>
    </div>
  );
}

export function PlainModelBadge(props: ModelBadgeProps) {
  const { version, className } = props;

  const modelIconURL = version?.properties?.model_icon as string | undefined;

  return (
    <div className={cn('flex h-full flex-row gap-[6px] overflow-hidden items-center', className)}>
      {!!modelIconURL && <Image src={modelIconURL} alt='' width={12} height={12} className='w-3 h-3 shrink-0' />}
      <div className='truncate whitespace-nowrap text-ellipsis overflow-hidden text-[13px] font-normal text-gray-500 min-w-0'>
        {version?.model}
      </div>
    </div>
  );
}
