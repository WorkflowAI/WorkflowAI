import { HoverCardContentProps } from '@radix-ui/react-hover-card';
import { TaskVersionBadgeContainer } from '@/components/TaskIterationBadge/TaskVersionBadgeContainer';
import { VersionV1 } from '@/types/workflowAI';
import { BaseOutputValueRow } from './BaseOutputValueRow';

type VersionOutputValueRowProps = {
  version: VersionV1 | undefined;
  side?: HoverCardContentProps['side'];
  showTaskIterationDetails?: boolean;
  isProxy?: boolean;
  hasProxyInput?: boolean;
};
export function VersionOutputValueRow(props: VersionOutputValueRowProps) {
  const { version, side, showTaskIterationDetails, isProxy, hasProxyInput } = props;

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
          isProxy={isProxy}
          hasProxyInput={hasProxyInput}
        />
      }
    />
  );
}
