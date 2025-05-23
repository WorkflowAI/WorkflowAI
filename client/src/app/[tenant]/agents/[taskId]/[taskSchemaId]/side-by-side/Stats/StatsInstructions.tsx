import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { SimpleTooltip } from '@/components/ui/Tooltip';
import { VersionV1 } from '@/types/workflowAI';

type StatsInstructionsProps = {
  version: VersionV1 | undefined;
  baseVersion: VersionV1 | undefined;
};

export function StatsInstructions(props: StatsInstructionsProps) {
  const { version, baseVersion } = props;

  if (version) {
    return (
      <SimpleTooltip
        content={<div className='max-w-[480px] max-h-[300px]'>{version.properties.instructions}</div>}
        tooltipClassName='whitespace-pre-line py-3 m-2 max-w-[80vh] max-h-[40vh] overflow-scroll'
        tooltipDelay={100}
      >
        <div className='flex w-full h-full items-center justify-start bg-white border border-gray-300 rounded-[2px] px-2 overflow-hidden my-2'>
          <div className='w-full text-gray-900 text-[13px] truncate'>{version.properties.instructions}</div>
        </div>
      </SimpleTooltip>
    );
  }

  if (baseVersion) {
    return (
      <div className='flex items-center gap-2 justify-start w-full h-full'>
        <div className='text-gray-900 text-[13px]'>Instructions match</div>
        <TaskVersionBadgeContainer
          version={baseVersion}
          showDetails={false}
          showNotes={false}
          showHoverState={false}
          showSchema={true}
          interaction={false}
          showFavorite={false}
        />
      </div>
    );
  }

  return <div className='flex items-center justify-start w-full h-full text-gray-500 text-[16px]'>-</div>;
}
