## Code

### How do I integrate a task in my codebase?

{% hint style="success" %}
For software engineers
{% endhint %}

We try to make it as easy as possible to integrate an AI Feature into your codebase.

1. Go to the Code page for your feature.
2. Select the coding language you want to use. Currently we support generating code for Python, Typescript, and REST API.
3. Select the version you want to use.
    - We highly recommend deploying a version to an environment before integrating it into your codebase. This way, your generated code will reference an environment variable instead of a hardcoded version number, allowing you to update the version without breaking changes.
4. If you have not already, install the WorkflowAI package, using the command provided on the code page.
5. Copy the code snippet and paste it into your codebase.
6. Create a secret key and paste it into the code snippet in your codebase.

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

You can enable result streaming from your AI Feature to reduce latency and enhance responsiveness. This is particularly useful for user-facing interactions, where shorter wait times significantly improve the overall user experience, since streaming ensures users see results progressively, rather than waiting for the entire output to load at once.

To enable streaming for your AI Feature:
1. Go to the **Code** page for your feature
2. Select the version and coding language you'd like to use in your product
3. Under the **Streaming** section, confirm that streaming is enabled before copying and pasting the generated code snippet into your codebase.