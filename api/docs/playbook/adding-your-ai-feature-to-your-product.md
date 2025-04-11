# Adding your AI Feature to your Product (and Beyond)

After finding a suitable version of the feature, it can be integrated into your product by deploying it.

## Deploying a Version

Once a suitable version is identified, the recommended next step is deploying the version to a WorkflowAI environment. WorkflowAI provides three environment options: dev, staging, production. A single version can be deployed to one or multiple environments.

Deploying a version enables your product’s codebase to reference the version with an environment variable (any of the three mentioned above) rather than a hardcoded version number. Using environment variables simplifies the process of updating versions; updating a deployed version on WorkflowAI automatically updates the version the environment variable references within your product. No engineering intervention required!

*Note: deploying a version on a different schema will require a code update. Schema updates are considered breaking changes, thus necessitating hardcoded version numbers in the product's codebase.*

## Integrating Your WorkflowAI Feature into Your Codebase 
{% hint style="success" %}
For software engineers
{% endhint %}

After deploying your chosen version to an environment: 
1. Go to the Code page.
2. Select your programming language.
3. Install the WorkflowAI package
4. Copy the provided integration code and paste into your codebase. Be sure to select the desired **version with the desired environment icon** from the version-selection dropdown to ensure the correct version is referenced in the generated code.

### Monitoring Runs
Once deployed, it’s recommended to monitor real-time feature runs (via the [Runs](../concepts/runs.md) page) through WorkflowAI to help identify and rectify early issues. All Runs of a feature are logged automatically on the Run’s page, so they can be accessed and viewed any time.

If issues with the feature are observed, refer to the [Improving your AI Feature](improving-your-ai-feature.md) section for common issues and tips on how to resolve them.

## Integrating WorkflowAI Feedback into Your Codebase 

{% hint style="success" %}
For software engineers
{% endhint %}

After integrating the feature into your product, consider integrating WorkflowAI's [feedback component](../features/user-feedback.md) into your product to collect user insights directly. The feedback component allows you to easily collect user feedback on your WorkflowAI feature to inform ongoing feature improvement.

### Monitoring Feedback

User feedback is essential for continuous improvement. Monitoring responses through WorkflowAI’s feedback system helps determine where enhancements are needed. The WorkflowAI feedback integration also connects to Slack so you'll be able to have user feedback sent from the WorkflowAI web app to Slack to make it easier to discuss the feedback insights with your team.