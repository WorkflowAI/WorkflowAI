import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { VersionV1 } from '@/types/workflowAI';
import { BaseOutputValueRow } from './BaseOutputValueRow';

type VersionOutputValueRowProps = {
  version: VersionV1 | undefined;
  side?: HoverCardContentProps['side'];
  showTaskIterationDetails?: boolean;
  setVersionIdForCode?: (versionId: string | undefined) => void;
};

export function VersionOutputValueRow(props: VersionOutputValueRowProps) {
  const { version, side, showTaskIterationDetails, setVersionIdForCode } = props;

  if (version === undefined) {
    return <BaseOutputValueRow label='Version' variant='empty' value='-' />;
  }

  return (
    <BaseOutputValueRow
      label='Version'
      value={
        <TaskVersionBadgeContainer
          version={version}
          side={side}
          showDetails={showTaskIterationDetails}
          setVersionIdForCode={setVersionIdForCode}
        />
      }
    />
  );
}
