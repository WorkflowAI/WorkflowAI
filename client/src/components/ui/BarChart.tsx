'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  Bar,
  CartesianGrid,
  LabelList,
  BarChart as RechartsBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { cn } from '@/lib/utils';

export const description = 'A bar chart with a label';

function formatValue(value: number, fractionalPart?: number, hideWhenItsFraction: boolean = false): string {
  if (value === 0) return '0';

  if (hideWhenItsFraction && value % 1 !== 0) return '';

  if (fractionalPart === undefined) return value.toLocaleString();

  const roundedValue = Number(value.toFixed(fractionalPart));

  if (roundedValue !== 0)
    return roundedValue.toLocaleString(undefined, {
      minimumFractionDigits: fractionalPart,
      maximumFractionDigits: fractionalPart,
    });

  // Find the first non-zero digit
  let precision = fractionalPart;
  while (Number(value.toFixed(precision)) === 0 && precision < 20) {
    precision++;
  }

  // Return the value with the precision that shows the first non-zero digit
  return value.toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}

type BarChartProps = {
  className?: string;
  height?: number;
  data: { x: string; y: number }[];
  fractionalPart?: number;
  prefix?: string;
  textColor?: string;
  barColor?: string;
  showValueAboveBar?: boolean;
  showTooltips?: boolean;
  barRadius?: number;
  hideFractionsOnYAxis?: boolean;
  tooltipLabel: string;
  showXAxisLabels?: boolean;
  minimalWidthForLabels?: number;
  turnOffFocus?: boolean;
  turnOffHorizontalLines?: boolean;
};

export function BarChart(props: BarChartProps) {
  const {
    data,
    className,
    height = 280,
    fractionalPart,
    prefix,
    textColor,
    barColor,
    showValueAboveBar = true,
    showTooltips = false,
    barRadius = 8,
    hideFractionsOnYAxis = false,
    tooltipLabel,
    turnOffFocus = false,
    turnOffHorizontalLines = false,
  } = props;

  const areAllTheValuesZero = useMemo(() => data.every((item) => item.y === 0), [data]);

  const [containerWidth, setContainerWidth] = useState(0);

  const handleResize = useCallback((width: number) => {
    setContainerWidth(width);
  }, []);

  const shouldShowLabels = useMemo(() => {
    const sizePerLabel = containerWidth / data.length;
    return sizePerLabel > 30;
  }, [containerWidth, data.length]);

  const showAxisLine = areAllTheValuesZero || turnOffHorizontalLines;

  return (
    <ResponsiveContainer
      width='100%'
      height={height}
      className={cn(className, turnOffFocus && 'no-focus')}
      onResize={handleResize}
    >
      <RechartsBarChart
        accessibilityLayer
        data={data}
        margin={{
          top: 20,
        }}
      >
        <CartesianGrid vertical={false} horizontal={!turnOffHorizontalLines} />
        <XAxis
          dataKey='x'
          stroke={textColor}
          fontSize={10}
          className='font-lato'
          tickLine={false}
          axisLine={showAxisLine}
          interval={0}
          tick={({ x, y, payload }) => {
            return (
              <text
                x={x}
                y={y}
                dy={16}
                textAnchor='middle'
                fill={textColor}
                fontSize={10}
                className='font-lato'
                opacity={shouldShowLabels ? 1 : 0}
              >
                {payload.value}
              </text>
            );
          }}
        />
        <YAxis
          stroke={textColor}
          fontSize={10}
          className='font-lato'
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => {
            return `${prefix ?? ''}${formatValue(value, fractionalPart, hideFractionsOnYAxis)}`;
          }}
        />

        {showTooltips && (
          <Tooltip
            formatter={(value: number) => [
              <div key='tooltip' className='flex justify-between w-full'>
                <div className='text-xs font-medium font-lato text-gray-500'>{tooltipLabel}</div>
                <div className='text-xs font-semibold font-lato text-gray-700'>
                  {`${prefix ?? ''}${formatValue(value, fractionalPart)}`}
                </div>
              </div>,
            ]}
            labelClassName='text-sm font-semibold font-lato text-gray-900 pb-1.5'
            labelStyle={{ color: '#334155' }}
            contentStyle={{
              backgroundColor: '#ffffff',
              color: '#334155',
              border: '1px solid #cbd5e1',
              borderRadius: '2px',
              padding: '6px 8px',
              boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
              minWidth: '158px',
            }}
            cursor={{ fill: 'transparent' }}
          />
        )}

        <Bar
          dataKey='y'
          fill={barColor}
          radius={[barRadius, barRadius, 0, 0]}
          isAnimationActive={false}
          activeBar={{ fill: '#4338CA' }}
        >
          {showValueAboveBar && !areAllTheValuesZero && (
            <LabelList
              position='top'
              offset={12}
              fontSize={12}
              formatter={(value: number) => `${prefix ?? ''}${formatValue(value, fractionalPart)}`}
              style={{
                fill: textColor,
                fontSize: '12px',
              }}
              className='font-lato'
            />
          )}
        </Bar>
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
