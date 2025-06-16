# Evaluate agents

## Introduction

## Simple one-shoot agents



## Chatbot agents

(i'm not sure we are equipped to evaluate chatbot agents yet)

## Agentic agents

(i'm not sure we are equipped to evaluate agentic agents yet)

## Doc 1.0

When it comes evaluating the runs of AI feature, there are two types of features:

- Features that are very easy to generate inputs for on the playground
- Features that require more complicated, real-world inputs to evaluate

Before spending time reviewing your runs, first determine if the feature can be accurately evaluated using runs with generated data from the playground, or if an early deployment to an internal beta is necessary in order to evaluate your feature using real data.

{% hint style="info" %}
At this time, evaluations are not available for proxy features, however we are working on adding this functionality soon.
{% endhint %}

## Reviewing Runs

Individual runs outputs can be evaluated on whether their output is correct or incorrect for a given input or not. This creates a quantitative baseline to determine feature accuracy on different versions.

Runs can be reviewed in two places:
- **Playground:** if the feature is easy to test using generated inputs, runs can be reviewed on the playground as they’re completed
- **Runs Page:** if runs are coming from the API/SDK (or if you want to add a review from the playground after the fact), runs can be reviewed any time after they’re completed from the Runs page. 

There are two types of reviews:
- **Human-Review:** a human reviewer manually evaluates a run and marks it as correct or incorrect. When a human review is left, you will see that the corresponding icon and background are solid.

![Human Review](../assets/images/reviews/human-review.png)

- **AI-Powered Review:** an AI agent evaluates a run and marks it as correct or incorrect. AI-powered reviews require an initial human review on the same input as a baseline for the AI review. When an AI review is left, you will see that the corresponding icon is highlighted, but not filled in. 

AI reviews can always be overriden by a human reviewer, so if something does not look right, you can correct the review.

![AI Review](../assets/images/reviews/ai-review.png)

{% hint style="info" %}
**What's the point of AI-powered reviews?**

AI-powered reviews save time by automatically reviewing runs with an input that matches an already human-reviewed run. So when you're iterating on your prompt with the same input, you won't need to manually review every single run.

AI-powered reviews are also used to calculate accuracy scores for versions when benchmarking. [Learn more about how benchmarking works.](#benchmarking-versions)
{% endhint %}

### Why is reviewing runs important?

When you leave a review on a run, you're adding that input/output pair - and whether is it correct - to your Reviews dataset. This dataset is used to benchmark the performance of different versions of your feature. The more runs that are evaluated, the larger your Reviews dataset will be, which will create a more accurate result for your benchmarks.

[Learn more about how benchmarking works.](#benchmarking-versions)

Additionally, the more reviews that are added, the more the AI reviewer agent will understand all the criteria that determines correctness for your feature, and it will be able to handle evaluating runs on your behalf more effectively.

### Can more than one output be considered correct?

In many cases, yes. For example, if there is a feature meant to summarize an article, there may be multiple summaries that contain all the correct information, but are phrased differently. In these cases, it's helpful to leave a review on all correct outputs. The multiple reviews help the AI reviewer agent get a better understanding of all the critieria that determines correctness.

### How big should my evaluation dataset be? How many runs should I review?

In most cases, we recommend reviewing 10-20 separate inputs to build an initial dataset. However the actual number may vary depending on your use case. The more complicated your feature is, the more reviews should be added to ensure that you have a robust dataset that covers all your important use cases. 

## Benchmarking Versions

![Benchmarks](../assets/images/benchmarks/benchmark-table.png)

Benchmarking evaluates performance on a version level by comparing different versions' performance, helping to identify the most effective versions based on accuracy, cost, and latency.

Benchmarks use the [reviews](#reviewing-runs) added about individual runs to calculate the overall accuracy of a version based on how many runs were viewed as correct vs. incorrect.

### How do I benchmark an AI Feature?

In order to benchmark an AI Feature, you need to have two things:
- Reviewed runs (we recommend starting with between 10-20 reviews, depending on the complexity of your AI Feature). You can learn more about how to review runs [here](../features/reviews.md).
- At least two saved versions of the AI Feature on the same Schema. To save a version, locate a run on the Playground or Runs page and select the "Save" button. This will save the parameters (instructions, temperature, etc.) and model combination used for that run.

After creating a review dataset and saving versions of your AI feature that you want to benchmark, access the Benchmark page in WorkflowAI's sidebar and select the versions you want to compare. The content of your review dataset will automatically be applied to all selected versions to ensure that they are all evaluated using the same criteria.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/14bbdd92a717ff4b224f82e57bdfca09/watch" %}

### How exactly does benchmarking work?

#### Accuracy

Version accuracy is based off of the human reviews left on runs and supplimented by AI-powered reviews. The process goes as such:

1. AI feature runs are given reviews by a human reviewer. The review runs are added to the Reviews dataset page (visible on the [Reviews page](../features/reviews.md)).
2. When benchmarking a version, the selected version runs all the inputs present in the Reviews dataset.
3. Using the human reviews from the dataset as a baseline, the AI-powered reviews are added to evaluate any runs on the benchmarked version that don't yet have a human review.
4. The amount of correct and incorrect runs - based on both the human reviews and AI-powered reviews - are used to calculate the accuracy of the version.

#### Price
Price is calculated based on the number of tokens used in the version's runs and cost of the tokens for the selected model.

#### Latency
Latency is calculated based on the time it takes for each of the version's runs to complete.

### How can I add a specific input to my benchmark evaluation dataset?

If there are inputs that you want to ensure are included when benchmarking a version, all you need to do is review at least one run of that input. Once an input has been reviewed, it will be automatically be added to your Reviews dataset and ultilized when benchmarking.

### A new model was released, how can I quickly evaluate it?

We're actively working on an even faster way to evaluate new models, but in the meantime here is the current process we recommend:

To quickly benchmark a new model:
1. Locate the feature you want to test the new model on
2. Make sure the schema selected in the header matches the schema you have deployed currently. 
3. Go to the versions page and locate your currently deployed version (you will recognize it by the environment icon(s) next to the number)
4. Hover over the version and select **Clone** and then select the new model.
5. Go to the benchmark page and select both the currently deployed version and the new version you just created.

Note: in order to ensure that a benchmark generates a fair and accurate comparison, it's important that you have a large enough evaluation dataset. See [How big should my evaluation dataset be/how many runs should I review?](#how-big-should-my-evaluation-dataset-be-how-many-runs-should-i-review) for more information.