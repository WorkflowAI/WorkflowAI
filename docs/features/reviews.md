## Reviews

Reviewing runs is a way to evaluate whether an individual run's output is correct or incorrect based on the given input. 

There are two types of reviews:
- **Human-Reviewed:** a human reviewer manually evaluates a run and marks it as correct or incorrect.

![Human Review](../assets/images/reviews/human-review.png)

- **AI-Reviewed:** an AI agent evaluates a run and marks it as correct or incorrect. AI reviews require a human review on the same input in order to run, as the human review is used as a baseline for the AI review.

![AI Review](../assets/images/reviews/ai-review.png)

### Why is reviewing runs important?

When you leave a review on a run, you're adding that input/output pair - and whether is it correct - to your Reviews dataset. This dataset is used to benchmark the performance of different versions of your feature. The more runs that are evaluated, the larger your Reviews dataset will be, which will create a more accurate result for your benchmarks.

[Learn more about how benchmarking works.](../features/benchmarks.md)

Additionally, the more reviews that are added, the more the AI reviewer agent will understand all the criteria that determines correctness for your feature, and it will be able to handle evaluating runs on your behalf more effectively.


### How do I review runs?
Before you can leave any reviews, you have to run your AI feature first. You can create runs from the [Playground](../features/playground.md) or from our [Python SDK](../sdk/python/get-started.md).

Runs can be reviewed in two places:
- **Playground:** if the feature is easy to test using generated inputs, runs can be reviewed on the playground as they’re completed. Just locate the green thumbs up and red thumbs down icon under the run output, and select the appropriate option.

- **Runs Page:** if runs are coming from the API/SDK (or if you want to add a review from the playground after the fact), runs can be reviewed any time after they’re completed from the Runs page. To review a run, locate the run and select it to open the run details page. Then, select the green thumbs up or red thumbs down icon under the run output to add a review.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/25b7b76eb1f4c407f67603f76279e00a/watch" %}

### Why do some of the review icons look different?

There are two types of reviews:
- **Human-Review:** a human reviewer manually evaluates a run and marks it as correct or incorrect. When a human review is left, you will see that the corresponding icon and background are solid.

![Human Review](../assets/images/reviews/human-review.png)

- **AI-Powered Review:** an AI agent evaluates a run and marks it as correct or incorrect. AI-powered reviews require an initial human review on the same input as a baseline for the AI review. When an AI review is left, you will see that the corresponding icon is highlighted, but not filled in. 

AI reviews can always be overriden by a human reviewer, so if something does not look right, you can correct the review.

![AI Review](../assets/images/reviews/ai-review.png)

{% hint style="info" %}

**What's the point of AI-powered reviews?**

AI-powered reviews save time by automatically reviewing runs with an input that matches an already human-reviewed run. So when you're iterating on your prompt with the same input, you won't need to manually review every single run.

AI-powered reviews are also used to calculate accuracy scores for versions when benchmarking. [Learn more about how benchmarking works.](../features/benchmarks.md)
{% endhint %}

### Can more than one output be considered correct?

In many cases, yes. For example, if there is a feature meant to summarize an article, there may be multiple summaries that contain all the correct information, but are phrased differently. In these cases, it's helpful to leave a review on all correct outputs. The multiple reviews help the AI reviewer agent get a better understanding of all the critieria that determines correctness.

### How big should my evaluation dataset be? How many runs should I review?

In most cases, we recommend reviewing 10-20 separate inputs to build an initial dataset. However the actual number may vary depending on your use case. The more complicated your feature is, the more reviews should be added to ensure that you have a robust dataset that covers all your important use cases.  
