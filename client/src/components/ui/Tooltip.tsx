'use client';

import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import * as React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { cn } from '@/lib/utils/cn';

const TooltipProvider = TooltipPrimitive.Provider;

const Tooltip = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      'z-50 overflow-hidden rounded-[3px] bg-gray-700 text-white px-3 py-1.5 text-[13px] font-lato font-normal shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2',
      className
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

type SimpleTooltipProps = {
  onOpenChange?: (open: boolean) => void;
  align?: 'start' | 'center' | 'end' | undefined;
  content: React.ReactNode | string | undefined;
  children: React.ReactNode;
  asChild?: boolean;
  supportClick?: boolean;
  side?: 'top' | 'bottom' | 'left' | 'right';
  tooltipClassName?: string;
  tooltipDelay?: number;
  forceShowing?: boolean;
  triggerClassName?: string;
};

function SimpleTooltip({
  onOpenChange,
  align,
  content,
  children,
  asChild = true,
  supportClick = false,
  side,
  tooltipClassName,
  tooltipDelay,
  forceShowing = false,
  triggerClassName,
}: SimpleTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isOpenFromClick, setIsOpenFromClick] = useState(false);

  useEffect(() => {
    const handleClickOutside = () => {
      setIsOpenFromClick(false);
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const internalOnOpenChange = useCallback(
    (open: boolean) => {
      onOpenChange?.(open);
      setIsOpen(open);
    },
    [onOpenChange]
  );

  if (!content) {
    return children;
  }

  return (
    <TooltipProvider delayDuration={tooltipDelay}>
      <Tooltip open={isOpen || isOpenFromClick || forceShowing} onOpenChange={internalOnOpenChange}>
        <TooltipTrigger
          data-testid='tooltip-trigger'
          asChild={asChild}
          onClick={supportClick ? () => setIsOpenFromClick(!isOpenFromClick) : undefined}
          className={triggerClassName}
        >
          {children}
        </TooltipTrigger>
        <TooltipContent
          data-testid='tooltip-content'
          align={align}
          side={side}
          className={tooltipClassName}
          avoidCollisions={true}
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider, SimpleTooltip };
