'use client';

import { FluentIcon } from '@fluentui/react-icons';
import { Slot } from '@radix-ui/react-slot';
import { type VariantProps, cva } from 'class-variance-authority';
import { Loader2, LucideIcon } from 'lucide-react';
import Link from 'next/link';
import * as React from 'react';
import { ReactElement, useCallback, useState } from 'react';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-[2px] text-[13px] font-semibold ring-offset-background transition-colors focus-visible:outline-none disabled:pointer-events-none gap-1.5',
  {
    variants: {
      variant: {
        default: 'bg-primary text-white hover:bg-primary/90 disabled:bg-slate-300',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90 disabled:bg-red-300',
        destructiveBorderOnly:
          'bg-white text-red-600 hover:bg-destructive/90 hover:text-white border hover:border-red-600 border-red-200',
        outline:
          'border border-input bg-background hover:bg-accent hover:text-accent-foreground text-slate-700 disabled:bg-slate-100 disabled:text-slate-400',
        subtle: 'bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:bg-slate-100 disabled:text-slate-400',
        ghost: 'text-gray-900 hover:bg-accent hover:text-accent-foreground disabled:text-slate-400',
        link: 'text-grey-800 underline-offset-[2px] underline disabled:text-grey-400',
        // TODO - remove this variant from the codebase as it is not part of the new design system
        offwhite: 'bg-slate-50 text-slate-500 hover:bg-slate-200/60 border-slate-200 border',
        text: 'text-slate-700 hover:text-slate-500',
        newDesign:
          'text-gray-900 border-gray-300 shadow-sm border border-input bg-background hover:bg-gray-100 disabled:bg-gray-100 disabled:text-gray-400',
        newDesignIndigo:
          'text-white shadow-sm border-none bg-custom-indigo-gradient hover:bg-custom-indigo-gradient-hover disabled:bg-custom-indigo-gradient disabled:text-white disabled:opacity-50',
        newDesignDark:
          'text-white shadow-sm border-none bg-gray-800 hover:bg-gray-600 disabled:bg-gray-400 text-white disabled:opacity-50',
        newDesignGray:
          'text-gray-800 border-none bg-gray-100 hover:bg-gray-200 disabled:bg-gray-100 disabled:text-gray-400 disabled:opacity-50',
        newDesignText: 'text-gray-900 hover:text-gray-500 disabled:text-gray-400',
        none: '',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-7 text-xs px-2 py-1',
        lg: 'h-11 text-md px-5 py-2',
        'icon-sm': 'h-7 w-7',
        'icon-lg': 'h-11 w-11',
        icon: 'h-9 w-9',
        none: '',
      },
      shape: {
        default: '',
        circle: 'rounded-full flex items-center justify-center',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

function getLucideIconSize(size: VariantProps<typeof buttonVariants>['size']) {
  switch (size) {
    case 'icon-lg':
    case 'lg':
      return 24;
    case 'icon':
      return 16;
    case 'icon-sm':
    case 'sm':
      return 12;
    default:
      return 16;
  }
}

function getFluentIconClassName(size: VariantProps<typeof buttonVariants>['size']) {
  switch (size) {
    case 'icon-lg':
    case 'lg':
      return 'w-6 h-6';
    case 'icon':
      return 'w-4 h-4';
    case 'icon-sm':
    case 'sm':
      return 'w-3 h-3';
    default:
      return 'w-4 h-4';
  }
}

type ButtonIconProps = {
  icon?: ReactElement | React.ReactNode;
  lucideIcon?: LucideIcon;
  fluentIcon?: FluentIcon;
  size?: VariantProps<typeof buttonVariants>['size'];
};

function ButtonIcon(props: ButtonIconProps) {
  const { icon, lucideIcon: LucideIconProp, fluentIcon: FluentIconProp, size } = props;
  if (LucideIconProp) {
    return <LucideIconProp size={getLucideIconSize(size)} />;
  }
  if (FluentIconProp) {
    return <FluentIconProp className={getFluentIconClassName(size)} />;
  }
  return icon;
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants>,
    ButtonIconProps {
  asChild?: boolean;
  loading?: boolean;
  toRoute?: string;
  openInNewTab?: boolean;
  target?: string;
  rel?: string;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading: externalLoading,
      toRoute,
      lucideIcon,
      fluentIcon,
      icon,
      children,
      onClick,
      disabled,
      shape,
      openInNewTab = false,
      target,
      rel,
      ...props
    },
    ref
  ) => {
    const [asyncOnClickLoading, setAsyncOnClickLoading] = useState(false);
    const finalOnClick = useCallback(
      (e: React.MouseEvent<HTMLButtonElement>) => {
        if (!onClick) return;
        const result = onClick(e);
        // If onClick is a promise, set loading to true until the promise resolves
        // @ts-expect-error -- it's fine if result is a promise
        if (result instanceof Promise) {
          setAsyncOnClickLoading(true);
          result.finally(() => setAsyncOnClickLoading(false));
        }
      },
      [onClick]
    );
    const loading = externalLoading || asyncOnClickLoading;

    const Comp = asChild ? Slot : 'button';
    const content = (
      <Comp
        className={cn(buttonVariants({ variant, size, shape, className }))}
        onClick={finalOnClick}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Loader2 className='h-4 w-4 animate-spin' />}
        {!loading && <ButtonIcon icon={icon} lucideIcon={lucideIcon} fluentIcon={fluentIcon} size={size} />}
        {children}
      </Comp>
    );

    return toRoute ? (
      toRoute.startsWith('mailto:') ? (
        <a href={toRoute} className={className} target={target || (openInNewTab ? '_blank' : undefined)} rel={rel}>
          {content}
        </a>
      ) : (
        <Link href={toRoute} className={className} target={target || (openInNewTab ? '_blank' : undefined)} rel={rel}>
          {content}
        </Link>
      )
    ) : (
      content
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
