import { LatencyOutputValueRow } from '../../playground/components/Tab/Output/TaskRunOutputRows/LatencyOutputValueRow';
import { PriceOutputValueRow } from '../../playground/components/Tab/Output/TaskRunOutputRows/PriceOutputValueRow';
import { SideBySideRowStats } from './useSideBySideRowStatsEffect';

type SideBySideTableRowOutputStatsProps = {
  stats: SideBySideRowStats;
};

export function SideBySideTableRowOutputStats(props: SideBySideTableRowOutputStatsProps) {
  const { stats } = props;

  return (
    <div className='flex flex-row'>
      <div className='flex flex-shrink-0'>
        <LatencyOutputValueRow
          currentAIModel={stats.model}
          minimumCostAIModel={stats.minimumCostModel}
          taskRun={stats.run}
          minimumLatencyTaskRun={stats.minimumLatencyRun}
          hideLabel
        />
      </div>
      <div className='flex flex-shrink-0'>
        <PriceOutputValueRow
          currentAIModel={stats.model}
          minimumCostAIModel={stats.minimumCostModel}
          taskRun={stats.run}
          minimumCostTaskRun={stats.minimumCostRun}
          hideLabel
        />
      </div>
    </div>
  );
}
