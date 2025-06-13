'use client';

import * as SliderPrimitive from '@radix-ui/react-slider';
import * as React from 'react';
import { cn } from '@/lib/utils/cn';

interface SliderProps extends React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> {
  rangeColor?: string;
  thumbBorderColor?: string;
  thumbSize?: string;
}

const Slider = React.forwardRef<React.ElementRef<typeof SliderPrimitive.Root>, SliderProps>(
  (
    { className, rangeColor = 'bg-gray-200', thumbBorderColor = 'border-gray-200', thumbSize = 'h-4 w-4', ...props },
    ref
  ) => (
    <SliderPrimitive.Root
      ref={ref}
      className={cn('relative flex w-full touch-none select-none items-center', className)}
      {...props}
    >
      <SliderPrimitive.Track className='relative h-1 w-full grow overflow-hidden rounded-full bg-gray-200'>
        <SliderPrimitive.Range className={cn('absolute h-full', rangeColor)} />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className={cn(
          'block rounded-full border bg-background ring-offset-background transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
          thumbSize,
          thumbBorderColor
        )}
      />
    </SliderPrimitive.Root>
  )
);
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
