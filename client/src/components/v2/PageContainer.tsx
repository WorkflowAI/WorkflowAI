import { useCopyCurrentUrl } from '@/lib/hooks/useCopy';
import { cn } from '@/lib/utils';
import { TaskSchemaID } from '@/types/aliases';
import { SerializableTask } from '@/types/workflowAI';
import { Loader } from '../ui/Loader';
import { ExtendedBordersContainer } from './ExtendedBordersContainer';
import { PageHeader } from './PageHeader/PageHeader';
import { PageHeaderRightComponents } from './PageHeader/PageHeaderRightComponents';

type PageContainerProps = {
  children: React.ReactNode;
  rightBarChildren?: React.ReactNode;
  rightBarText?: string;
  task: SerializableTask | undefined;
  isInitialized: boolean;
  name: string | React.ReactNode;
  showCopyLink?: boolean;
  showBottomBorder?: boolean;
  extraButton?: React.ReactNode;
  showSchema?: boolean;
  documentationLink?: string;
  showBorders?: boolean;
  schemaId?: TaskSchemaID;
  documentationText?: string;
};

export function PageContainer(props: PageContainerProps) {
  const {
    children,
    rightBarChildren,
    rightBarText,
    task,
    isInitialized,
    name,
    showCopyLink = false,
    showBottomBorder = true,
    extraButton,
    showSchema = true,
    documentationLink,
    showBorders = true,
    schemaId,
    documentationText,
  } = props;

  const copyUrl = useCopyCurrentUrl();

  const margin = showBorders ? 24 : 0;
  const borderColor = showBorders ? 'gray-100' : 'clear';

  if (!isInitialized) {
    return <Loader centered />;
  }

  if (!task) {
    return (
      <div className='flex flex-col h-full w-full font-lato p-6'>
        <ExtendedBordersContainer className='flex flex-col h-full w-full' borderColor={borderColor} margin={margin}>
          <div
            className={cn(
              'flex items-center justify-between h-[60px] w-full flex-shrink-0 px-4 font-semibold text-base text-gray-700',
              showBottomBorder && 'border-b border-dashed border-gray-200'
            )}
          >
            <div>{name}</div>
            <div>{rightBarChildren}</div>
          </div>
          <div className='flex h-[calc(100%-60px)] w-full'>{children}</div>
        </ExtendedBordersContainer>
      </div>
    );
  }

  return (
    <div className='flex flex-col h-full w-full font-lato sm:p-6 p-0'>
      <ExtendedBordersContainer className='flex flex-col h-full w-full' borderColor={borderColor} margin={margin}>
        <PageHeader
          task={task}
          schemaId={schemaId}
          name={name}
          documentationLink={documentationLink}
          className={cn(
            'flex items-center gap-2 min-h-[60px] overflow-hidden',
            showBottomBorder && 'border-b border-dashed border-gray-200'
          )}
          showSchema={showSchema}
        >
          <PageHeaderRightComponents
            name={name}
            rightBarText={rightBarText}
            documentationLink={documentationLink}
            documentationText={documentationText}
            extraButton={extraButton}
            showCopyLink={showCopyLink}
            copyUrl={copyUrl}
            rightBarChildren={rightBarChildren}
          />
        </PageHeader>
        <div className='flex sm:h-[calc(100%-60px)] h-[calc(100%-126px)] w-full'>{children}</div>
      </ExtendedBordersContainer>
    </div>
  );
}
