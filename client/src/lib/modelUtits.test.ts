import { embedReasoningInModelID, extractReasoningFromModelID } from './modelUtils';

describe('modelUtils', () => {
  describe('extractReasoningFromModelID', () => {
    it('should extract the reasoning from the model ID', () => {
      expect(extractReasoningFromModelID('model-low-reasoning')).toEqual(['model', 'low']);
    });

    it('extracts post embed reasoning', () => {
      expect(extractReasoningFromModelID('model-low-reasoning')).toEqual(['model', 'low']);
    });

    it('returns undefined if no reasoning', () => {
      expect(extractReasoningFromModelID('model')).toEqual(['model', undefined]);
    });
  });

  describe('embedReasoningInModelID', () => {
    it('embeds reasoning in the model ID', () => {
      expect(embedReasoningInModelID('model', 'low')).toEqual('model-low-reasoning');
    });
  });
});
