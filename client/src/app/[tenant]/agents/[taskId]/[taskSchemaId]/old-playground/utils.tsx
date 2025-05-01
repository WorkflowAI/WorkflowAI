import { Review } from '@/types/workflowAI';

type CombineReviewAspectsProps = {
  review: Review;
};

export function combineReviewAspects(props: CombineReviewAspectsProps): string {
  const { review } = props;

  let beginning = '';
  switch (review.outcome) {
    case 'positive':
      beginning = 'My Review is overall “positive”';
      break;
    case 'negative':
      beginning = 'My Review is overall “negative”';
      break;
    default:
      beginning = 'My Review is overall “unsure”';
  }

  const positiveAspects = review.positive_aspects;
  const negativeAspects = review.negative_aspects;

  if (!positiveAspects && !negativeAspects) {
    return `${beginning}. Summary: ${review.summary}.`;
  }

  const positiveAspectsString = positiveAspects?.join(', ');
  const negativeAspectsString = negativeAspects?.join(', ');

  let result = beginning;

  if (positiveAspectsString && positiveAspectsString.length > 0) {
    result += `. Positive Aspects: ${positiveAspectsString}`;
  }

  if (negativeAspectsString && negativeAspectsString.length > 0) {
    result += `. Negative Aspects: ${negativeAspectsString}.`;
  }

  return result;
}
