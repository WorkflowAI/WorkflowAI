'use client';

import * as ProgressPrimitive from '@radix-ui/react-progress';
import * as React from 'react';
import { cn } from '@/lib/utils/cn';

export interface ProgressProps
  extends React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> {
  indicatorClassName?: string;
  animated?: boolean;
}

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  ProgressProps
>(
  (
    { className, value, indicatorClassName, animated = true, ...props },
    ref
  ) => (
    <ProgressPrimitive.Root
      ref={ref}
      className={cn(
        'relative h-1 w-full overflow-hidden rounded-full bg-gray-100',
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn(
          'h-full w-full flex-1 bg-indigo-600',
          animated && 'transition-transform',
          indicatorClassName
        )}
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  )
);

Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
