import { cn } from '@/lib/utils';

function getColor(intelligence: number, allIntelligenceScores: number[] | undefined) {
  if (!allIntelligenceScores?.length) return 'bg-gray-500';

  const sortedScores = [...allIntelligenceScores].sort((a, b) => b - a);
  const totalModels = sortedScores.length;
  const oneThird = Math.floor(totalModels / 3);

  const position = sortedScores.indexOf(intelligence);

  if (position < oneThird) return 'bg-green-500';
  if (position < oneThird * 2) return 'bg-yellow-400';
  return 'bg-red-500';
}

type IntelliganceProgressProps = {
  intelligence: number;
  allIntelligenceScores: number[] | undefined;
};

export function IntelliganceProgress(props: IntelliganceProgressProps) {
  const { intelligence, allIntelligenceScores } = props;

  const color = getColor(intelligence, allIntelligenceScores);
  return (
    <div className='flex flex-row h-full w-fit items-center'>
      <div className='flex flex-row flex-shrink-0 whitespace-nowrap items-center w-[40px] h-[8px]'>
        <div className='flex w-full h-2 bg-gray-200 rounded-[2px] overflow-clip'>
          <div className={cn('flex h-full', color)} style={{ width: (40 * intelligence) / 100 }} />
        </div>
      </div>
    </div>
  );
}
