## Code

TODO: needs re-write:
- code page shows code for all integrations
- should we split between our SDK and integrations?
- ...

### How do I integrate a task in my codebase?

We try to make it as easy as possible to integrate an AI agent into your codebase.

{% stepper %}

{% step %}
### Go to the Code page for your agent
Navigate to the Code page in your WorkflowAI dashboard.
{% endstep %}

{% step %}
### Select your coding language
Choose from Python, TypeScript, or REST API.
{% endstep %}

{% step %}
### Select the version you want to use
We highly recommend deploying a version to an environment before integrating it into your codebase. This way, your generated code will reference an environment variable instead of a hardcoded version number, allowing you to update the version without breaking changes.
{% endstep %}

{% step %}
### Install the WorkflowAI package
If you have not already, install the WorkflowAI package using the command provided on the code page.
{% endstep %}

{% step %}
### Copy the code snippet
Copy the generated code snippet and paste it into your codebase.
{% endstep %}

{% step %}
### Create and add a secret key
Create a secret key and paste it into the code snippet in your codebase.
{% endstep %}

{% endstepper %}

{% embed url="https://customer-turax1sz4f7wbpuv.cloudflarestream.com/fb48300ea1849cb54581c7797c0d2567/watch" %}

### Caching
| Option | Description |
| ------ | ----------- |
| `auto` (default) | Completions are cached only if they have `temperature=precise` (or `0`) |
| `always` | Completions are always cached, even if `temperature` is set to `Balanced` or `Creative` |
| `never` | The cache is never read or written to |

{% hint style="warning" %}
Even with `cache=never`, using `temperature=precise` will still produce consistent outputs because the AI model itself is deterministic at this setting. To get varied outputs, change the temperature to `Balanced` or `Creative` (or any value greater than 0).
{% endhint %}

### Streaming

You can enable result streaming from your AI agent to reduce latency and enhance responsiveness. This is particularly useful for user-facing interactions, where shorter wait times significantly improve the overall user experience, since streaming ensures users see results progressively, rather than waiting for the entire output to load at once.

To enable streaming for your AI agent:
1. Go to the **Code** page for your agent
2. Select the version and coding language you'd like to use in your product
3. Under the **Streaming** section, confirm that streaming is enabled before copying and pasting the generated code snippet into your codebase.