## Side by Side

Side by side is a minimal-setup-required feature that allows you to quickly compare how two different versions or models handle a different inputs.

### How to use Side by Side

While the goal of side by side is to be as minimal-setup-required as possible, there are a few prerequisites:
- You need to have at least one version of a feature saved.
- You need to have at least one input to compare, although we recommend having a minimum of 10 to provide a robust dataset to generate a comparison.

One you meet the above requirements, to use Side by Side:

1. Login to [WorkflowAI](https://workflowai.com/)
2. Select the AI feature and you want to compare
3. Visit the Side by Side page in the sidebar
4. In the left column, you will be able to see the inputs that will be used to generate the comparison. 
5. In the middle column, select the currently existing version of the feature you want to compare against (if you have a version of your AI feature deployed, you'd likely want to select the deployed version here).
6. In the right column, select the new model or version of the feature you want to compare against the existing version. 

Once you have selected the two versions, it may take a moment to run the inputs through the two versions and generate a comparison, but onces that's done, you'll be able to see how the two different versions handle the same inputs, side by side for easy comparison. 

{% hint style="info" %}
This feature is still in it's early stages of development, so more functionality will be added in the future. If there's something you'd like to see, please let us know on [GitHub](https://github.com/workflowai/workflowai/discussions) or [Discord](https://discord.gg/jSahs44g).
{% endhint %}

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/c5535f94084564ffc40e23182380d6ce/watch" %}

### What's the difference between Side-by-Side and Benchmarks?

In short: side by side is better at giving you a quick vibe check of a new version or model, while benchmarking is better at providing a more thorough evaluation across multiple versions.

With Side by Side, you can quickly compare the outputs of two different versions of an AI feature, but since side by side doesn't currently include any AI powered analysis or reviews, you will need to manually assess which version you think performs better. Side by side is also limited to comparing two versions at a time, meaning that you will to have a sense of which versions you want to compare against before you can use side by side.

Benchmarking, on the other hand, does include AI powered analysis and reviews to gauge which model is more accurate. However, in order to ensure that a benchmark generates a fair and useful accuracy score, it's important that you spend the time to build up a large enough evaluation dataset. See [How big should my evaluation dataset be/how many runs should I review?](#how-big-should-my-evaluation-dataset-behow-many-runs-should-i-review) for more information. Because of this need for a dataset, benchmarking is a more time-intensive process than side by side. Benchmarking also allows you to compare multiple versions at once, meaning that if you don't yet known which two versions or models you want to compare, you can simultaneously benchmark as many versions as you want and see which one(s) stand out. 

### Can I use Side by Side when a new model comes out?

Yes! We built Side by Side with this use case in mind. You can use Side by Side to get a quick vibe check of a new model compared to your currently deployed model. All you need to do is navigate to the Side by Side page and select the new model from the dropdown menu on the right. 
