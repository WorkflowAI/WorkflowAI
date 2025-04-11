## Reviews

Reviewing runs is a way to evaluate whether an individual run's output is correct or incorrect based on the given input. 

There are two types of reviews:
- **Human-Reviewed:** a human reviewer manually evaluates a run and marks it as correct or incorrect.

![Human Review](../assets/images/reviews/human-review.png)

- **AI-Reviewed:** an AI agent evaluates a run and marks it as correct or incorrect. AI reviews require a human review on the same input in order to run, as the human review is used as a baseline for the AI review.

![AI Review](../assets/images/reviews/ai-review.png)

### Why are reviews important?

Reviews create a quantitative baseline to determine how different versions handle the same input. Every run that is reviewed is added to your Review dataset. When you Benchmark a version, the content of your dataset - both the correct and incorrect runs - is used to determine how all Benchmarked versions handle the same input.


### How do I review runs?
Before you can leave any reviews, you have to run your AI feature first. You can create runs from the [Playground](../features/playground.md) or from our [Python SDK](../sdk/python/get-started.md).

Runs can be reviewed in two places:
- **Playground:** if the feature is easy to test using generated inputs, runs can be reviewed on the playground as they’re completed. Just locate the green thumbs up and red thumbs down icon under the run output, and select the appropriate option.

- **Runs Page:** if runs are coming from the API/SDK (or if you want to add a review from the playground after the fact), runs can be reviewed any time after they’re completed from the Runs page. To review a run, locate the run and select it to open the run details page. Then, select the green thumbs up or red thumbs down icon under the run output to add a review.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/25b7b76eb1f4c407f67603f76279e00a/watch" %}