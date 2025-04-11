## Benchmarks

Benchmarks are a way to find the best version of your agent based on a quantitative comparison of the performance, cost and latency of each version.

![Benchmarks](../assets/images/benchmarks/benchmark-table.png)

### How do I benchmark an AI Feature?

In order to benchmark an AI Feature, you need to have two things:
- Reviewed runs (we recommend starting with between 10-20 reviews, depending on the complexity of your AI Feature). You can learn more about how to review runs [here](../features/reviews.md).
- At least two saved versions of the AI Feature on the same Schema. To save a version, locate a run on the Playground or Runs page and select the "Save" button. This will save the parameters (instructions, temperature, etc.) and model combination used for that run.

After creating a review dataset and saving versions of your AI feature that you want to benchmark, go to the Benchmark page and select the versions you want to compare. The content of your review dataset will automatically be applied to all selected versions to ensure that they are all evaluated using the same criteria.

In addition to the accuracy of each version (which is calculated based on your review dataset), you the cost and latency of each version are also calculated.

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/14bbdd92a717ff4b224f82e57bdfca09/watch" %}