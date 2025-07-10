import { cn } from '@/lib/utils';

type Props = {
  children: React.ReactNode;
  className?: string;
};

export function FieldViewerAnnotationHoverContainer(props: Props) {
  const { children, className } = props;

  return <div className={cn(className, 'hover:bg-red-200')}>{children}</div>;
}
