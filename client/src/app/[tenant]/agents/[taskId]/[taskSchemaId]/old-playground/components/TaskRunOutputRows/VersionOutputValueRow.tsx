import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { VersionV1 } from '@/types/workflowAI';
import { BaseOutputValueRow } from './BaseOutputValueRow';

type VersionOutputValueRowProps = {
  version: VersionV1 | undefined;
  side?: HoverCardContentProps['side'];
  showTaskIterationDetails?: boolean;
};
export function VersionOutputValueRow({ version, side, showTaskIterationDetails }: VersionOutputValueRowProps) {
  if (version === undefined) {
    return <BaseOutputValueRow label='Version' variant='empty' value='-' />;
  }

  return (
    <BaseOutputValueRow
      label='Version'
      value={<TaskVersionBadgeContainer version={version} side={side} showDetails={showTaskIterationDetails} />}
    />
  );
}
