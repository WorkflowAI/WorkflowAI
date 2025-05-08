## Benchmarks

Benchmarks are a way to find the best version of your agent based on a quantitative comparison of the performance, cost and latency of each version.

![Benchmarks](../assets/images/benchmarks/benchmark-table.png)

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

Note: in order to ensure that a benchmark generates a fair and accurate comparison, it's important that you have a large enough evaluation dataset. See [How big should my evaluation dataset be/how many runs should I review?](../playbook/evaluating-your-ai-feature.md#how-big-should-my-evaluation-dataset-be-how-many-runs-should-i-review) for more information.