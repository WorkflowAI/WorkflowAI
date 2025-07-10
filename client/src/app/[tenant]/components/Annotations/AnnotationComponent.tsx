import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Annotation } from '@/types/workflowAI/models';
import { AnnotationButton } from './AnnotationButton';
import { AnnotationCreateComponent } from './AnnotationCreateComponent';
import { ExistingAnnotationView } from './ExistingAnnotationView';

type Props = {
  className?: string;
};

export function AnnotationComponent(props: Props) {
  const { className } = props;
  const [isOpen, setIsOpen] = useState(false);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);

  const onCreateAnnotation = (annotation: Annotation) => {
    setAnnotations([...annotations, annotation]);
    setIsOpen(false);
  };

  return (
    <div className={cn('flex flex-col gap-3 w-full', className)}>
      {annotations.map((annotation) => (
        <ExistingAnnotationView key={annotation.id} annotation={annotation} />
      ))}
      {isOpen ? (
        <AnnotationCreateComponent onCreateAnnotation={onCreateAnnotation} onCancel={() => setIsOpen(false)} />
      ) : (
        <div className='flex flex-row'>
          <AnnotationButton onClick={() => setIsOpen(true)} />
        </div>
      )}
    </div>
  );
}
