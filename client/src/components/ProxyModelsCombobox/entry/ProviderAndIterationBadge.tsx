import { AIProviderIcon } from '@/components/icons/models/AIProviderIcon';

type ProviderAndIterationBadgeProps = {
  providerId: string | null | undefined;
  iteration: number | undefined;
};

export function ProviderAndIterationBadge(props: ProviderAndIterationBadgeProps) {
  const { providerId, iteration } = props;

  return (
    <div
      className={
        'w-fit border border-gray-200 rounded-[2px] cursor-pointer hover:bg-accent hover:text-accent-foreground px-1.5 py-1 bg-white'
      }
    >
      <div className='flex items-center gap-1'>
        {providerId ? <AIProviderIcon providerId={providerId} fallbackOnMysteryIcon /> : null}
        <div className='text-[13px] font-medium text-gray-700 font-lato'>
          {iteration !== undefined && `${iteration}`}
        </div>
      </div>
    </div>
  );
}
