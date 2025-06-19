<PROMPT>
...
</PROMPT>

Take your time to think, find the simplest elegant solution, and write the correct amount of unit tests to help you along the way.

Do not over-engineer the solution, and write your code in a way that is easy to understand and maintain.

Write your process and interesting implement details in a new file in a .discussions/ folder and make sure to include this prompt as context.

Make sure the tests of files you're editing are passing. (and report back about the status of these tests in the .discussions/ file)

Make sure to read the instructions from the AGENT.md file in the root of the folder.

Do not set python.languageServer to "None" in .vscode/settings.json

The .discussions/ file should have the following structure:

<file>
# Goal of this PR

# Implementation decision

# Tests status

# Potential next steps

</file>

<IMPORTANT>
Before you commit, run the following commands on the files impacted by your changes and fix any issues:
```bash
poetry run ruff check <path-to-file>
poetry run pyright <path-to-file>
````

</IMPORTANT>

[branch=<BRANCH>]
