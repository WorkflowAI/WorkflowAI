import { Checkmark12Filled, Dismiss12Filled } from '@fluentui/react-icons';

type ReviewCommentAspectsRowProps = {
  aspect: string;
  state: string | undefined;
};

function ReviewCommentAspectsRow(props: ReviewCommentAspectsRowProps) {
  const { aspect, state } = props;

  return (
    <div className='flex flex-row justify-start items-start'>
      {state === 'negative' ? (
        <Dismiss12Filled className='text-red-600 w-3 h-3 ml-1 mr-1 mb-1 mt-0.5 flex-shrink-0' />
      ) : (
        <Checkmark12Filled className='text-green-700 w-3 h-3 ml-1 mr-1 mb-1 mt-0.5 flex-shrink-0' />
      )}
      <div className='text-gray-500 text-xs whitespace-pre-line overflow-hidden transition-all duration-200'>
        {aspect}
      </div>
    </div>
  );
}

type ReviewCommentAspectsProps = {
  aspects: string[] | undefined;
  state: string | undefined;
};

export function ReviewCommentAspects(props: ReviewCommentAspectsProps) {
  const { aspects, state } = props;

  if (!aspects || aspects.length === 0) {
    return null;
  }

  return (
    <div className='flex flex-col max-h-none px-3 py-2 border-t border-gray-200 border-dashed'>
      {aspects?.map((aspect) => <ReviewCommentAspectsRow aspect={aspect} state={state} key={aspect} />)}
    </div>
  );
}
