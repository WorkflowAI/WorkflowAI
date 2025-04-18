import { ModelBadge } from '@/components/ModelBadge/ModelBadge';
import { cn } from '@/lib/utils';
import { ModelResponse } from '@/types/workflowAI';

type SideBySideVersionPopoverModelItemProps = {
  model?: ModelResponse;
  onClick?: () => void;
  className?: string;
};

export function SideBySideVersionPopoverModelItem(props: SideBySideVersionPopoverModelItemProps) {
  const { model, onClick, className } = props;

  if (!model) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex flex-row items-center gap-1 rounded-[1px] hover:bg-gray-100 cursor-pointer px-2 py-1 overflow-hidden',
        className
      )}
      onClick={onClick}
    >
      {model && <ModelBadge model={model} />}
    </div>
  );
}
