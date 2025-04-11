# Evaluating your AI Feature

{% hint style="success" %}
For product and engineering teams
{% endhint %}

When it comes evaluating the runs of AI feature, there are two types of features:

- Features that are very easy to generate inputs for on the playground
- Features that require more complicated, real-world inputs to evaluate

Before spending time reviewing your runs, first determine if the feature can be accurately evaluated using runs with generated data from the playground, or if an early deployment to an internal beta is necessary in order to evaluate your feature using real data.

## Reviewing Runs

Individual runs outputs can be evaluated on whether their output is correct or incorrect for a given input or not. This creates a quantitative baseline to determine feature accuracy on different versions. The more runs that are evaluated, the more accurate version benchmarks - the next section - will be.

Runs can be reviewed in two places:
- **Playground:** if the feature is easy to test using generated inputs, runs can be reviewed on the playground as they’re completed
- **Runs Page:** if runs are coming from the API/SDK (or if you want to add a review from the playground after the fact), runs can be reviewed any time after they’re completed from the Runs page. 

## Benchmarking Versions

![Benchmarks](</docs/assets/images/benchmarks.png>)

Benchmarking evaluates performance on a version level by comparing different versions' performance, helping to identify the most effective versions based on accuracy, cost, and latency.

Benchmarks use the reviews added about individual runs to calculate the overall accuracy of a version based on how many runs were viewed as correct vs. incorrect. 

Versions can be benchmarked on the Benchmark page. When a version is selected to be benchmarked, inputs from all reviewed runs are rerun on the selected version to ensure that the benchmarked versions are all evaluated using the same criteria.
