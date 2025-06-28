import { useMemo } from 'react';
import { WorkflowAIIconWithCurrentColor } from '@/components/Logos/WorkflowAIIcon';

type PriceGraphProps = {
  price: number;
};

interface MarkerProps {
  price: number;
  showLabel: boolean;
}

function Marker(props: MarkerProps) {
  const { price, showLabel } = props;
  const formatPrice = (price: number) => `$${price.toFixed(2)}`;

  return (
    <div className='relative h-full'>
      <div className='w-[1px] h-full bg-gray-700' />
      {showLabel && (
        <div className='absolute bottom-[-24px] left-1/2 -translate-x-1/2 text-gray-500 text-xs whitespace-nowrap'>
          {formatPrice(price)}
        </div>
      )}
    </div>
  );
}

function roundToNice(num: number) {
  const magnitude = Math.pow(10, Math.floor(Math.log10(num)));
  return Math.ceil(num / magnitude) * magnitude;
}

function calculateMarkersAndWidth(price: number) {
  const maxValue = roundToNice(price * 1.2);
  const markers = [0, maxValue / 2, maxValue];

  const barWidth = (price / maxValue) * 100;

  return {
    markers,
    barWidth: Math.min(barWidth, 100),
  };
}

export function PriceGraph(props: PriceGraphProps) {
  const { price } = props;
  const { markers, barWidth } = useMemo(() => calculateMarkersAndWidth(price), [price]);

  return (
    <div className='flex flex-row gap-2 w-full items-start'>
      <div className='flex flex-col gap-2 items-end text-gray-300 text-[12px] py-1'>
        <div>Provider</div>
        <div className='flex flex-row gap-1 items-center'>
          <WorkflowAIIconWithCurrentColor ratio={0.7} />
          <div>WorkflowAI</div>
        </div>
      </div>
      <div className='w-full relative pb-7 mr-4'>
        <div className='absolute inset-0 flex justify-between pointer-events-none h-[53px]'>
          {markers.map((markerPrice, index) => (
            <Marker key={index} price={markerPrice} showLabel={index !== 0} />
          ))}
        </div>

        <div className='w-full flex flex-col gap-2 relative py-[2px]'>
          <div className='h-[20px] relative'>
            <div className='absolute h-full bg-gray-700 rounded-r-[2px]' style={{ width: `${barWidth}%` }} />
          </div>
          <div className='h-[20px] relative'>
            <div className='absolute h-full bg-indigo-800 rounded-r-[2px]' style={{ width: `${barWidth}%` }} />
          </div>
        </div>
      </div>
    </div>
  );
}
