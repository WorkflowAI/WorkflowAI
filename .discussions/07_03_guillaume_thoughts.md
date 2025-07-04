I did the exercise of "what would WorkflowAI be" if I was building it now with the advances in MCP and the experience of the past 2 years.

If I recall, we have always wanted to make the code the source of truth.

- the first WorkflowAI was a CLI
- we went back with it for a very brief time using the "agent builder" pattern
- we made the python SDK capable of auto-creating agents for that purpose
  etc.

But that was never satisfactory because we could not settle on a nice UX. MCP solves that problem and makes it possible.

Which means that now, we don't really need UX anymore. Only developer experience.
So we need to think about WorkflowAI as it would be used by developers, and by developers only. A developer can possibly be an agent.

So if we apply the principles of Dev UX to how we have built WorkflowAI, we made the mistake of thinking of features that are too high level and don't offer enough flexibility. Reviews are a good example. They are computed auto-magically and hide the concept of datasets.

So to rethink WorkflowAI as (basically) an SDK, we need to think about a very limited number of core primitives that can be organized by a developer.

Another thing that's interesting is that all the actions that can be performed on primitives should be possible via the UI, code and MCP in some form or another. I don't think it's a matter of **what action can be performed where**, but rather **how can the action be optimized for the different mediums**. For example, the "edit output" action is just **not part of WorkflowAI** period. It is the responsibility of the developer. Our responsibility is to provide the dev with the right tool and documentation.

# Primitives:

## Completions (aka run)

Core primitive of WorkflowAI. The actions that can be performed:

- creating a completion
- viewing a completion
- searching for completions (maybe manipulate the object via a raw SQL query, i.e., group by input, model, etc.)
- annotate a completion

A completion includes:

- request parameters (aka Versions): templated or system prompt, model, input variables, response format
- output: response, tool calls
- raw messages
- annotations (maybe we can start with a single annotation, and later have annotations per dimension (aka insight)). An annotation has a numerical value (0-1), with 0 being completely negative and 1 being completely positive.

## Versions

A version is a set of request parameters used to create a completion.

> I am not 100% sure that a version should be anything more than "part of a completion". For example, do we actually need to save versions?
> What's sure is that the focus should shift from "version" to "runs" in the sense that when I look at the version, what I am mostly interested in is the runs that this version created. And when I look at a version changelog, I am mostly interested in the impact the version change had on runs.

## Deployments

A deployment is an alias for a version that can be changed server side. A deployment can be updated to point to a different version only if the new version is compatible with the old version (aka would not require a code change)

I.e.:

- same tools
- same input schema
- same output schema

Actions:

- create deployment
- update deployment
- archive deployment (still usable just in case but no longer displayed in the UI)

## Experiments

An experiment is a group of runs that were triggered together with the intent of comparing them.
Every experiment has an AI-generated summary and can have human reviews.

Examples:

- re-run the last 50 runs from the production deployment using model N
- compare model X, Y, and Z on the dataset of input in my code
- re-run all the annotated runs

An experiment is "read only" in the sense that a run cannot be added to an experiment. Repeating an experiment is a new experiment.

## Iterate

Iterate (or Improve) should also be a primitive because it is also a core action in WorkflowAI. Iterate is the action of taking a set of runs and annotations and/or a comment, generating new runs and comparing the results.

An iterate action always results in an experiment.

# Flows

## Creating a new agent

1. (Cursor) Prompt to build the new agent
2. (MCP) MCP runs an experiment on the new agent on a single prompt using several models / inputs
3. (UI) User annotates the experiment in the UI
4. (Cursor / UI) trigger _iterate_
5. Rinse and repeat. The experiment review is important to direct the way the prompt is improved, focusing either on cost, latency, accuracy, etc.
6. (UI) Once the user is satisfied, they can deploy a version from the experiment
7. (Cursor) Back in cursor MCP get_code

## A new model comes out

1. (Cursor) Prompt the MCP to run the last 50 runs on the new model, compare the results and generate a report
2. (UI) When the report is complete, the user can go to the UI and review the comparison (in this case 1 prompt, 2 models, 50 inputs)
3. (UI) The user can decide to update the current deployment or not

> A/B testing with the deployment would be interesting here

## Run agents on existing dataset/batch runs (M1, Berrystreet, user from HelpScout Florian). **Agent already exists**

Dataset is committed through code in whatever format. GitHub will always be a better place to store a dataset. (Users could also connect whatever other database to their agents)

1. (Cursor) "Run the current production version on each input in _the dataset_. For every run, compare the output with the expected output and leave an annotation on the run" -> creates an experiment, generates a summary and reports back
2. (UI) View experiment and annotate run if needed
3. Iterate ...

## Run agents on existing dataset/batch runs (M1, Berrystreet, user from HelpScout Florian). **Agent does not exist**

1. (Cursor) Create an agent that will [...]. You can use this dataset as a reference.
   > Cursor should create a basic agent based on the request, pick n models and run it on the dataset. Creating an experiment, then annotate each
   > run based on the comparison with the expected output. To me the best would be to involve the user in the first iteration, to review
   > the experiment and run annotations
2. (UI) View experiment and correct annotations if needed
   > it would be interesting to keep the corrected annotations so that the evaluator can auto-correct
3. Iterate

## Analyze runs via a conversation with AI (Luni)

> This one is pretty obvious I think. The real question is who (Cursor or WorkflowAI) is going to answer questions on individual runs

1. (Cursor) "Can you tell me if the last 50 runs have a friendly tone"
2. (Cursor) fetches the last 50 runs and annotate each one (or our MCP has a tool call `probe_run(run_id, question)`)
3. (Cursor) computes the report
4. (UI) runs and annotations are visible in an experiment

## Leave written feedback on runs and have AI use the feedback to improve prompt (Xavier)

> That's the basic concept of annotations. Viewing runs in YAML and being able to inline comments would be insanely good.

1. (Cursor) "Checking all runs with annotations, can you see if you can improve the prompt?"
2. (Cursor) fetches all the runs with annotations, builds a new prompt and runs an experiment. Cursor can annotate each new run automatically
3. (UI) runs and annotations are visible in an experiment

> It is worth trying to have Cursor do the improve prompt itself. I am wondering if we will not run into context length / consistency issues.
> For example, it would likely be much more efficient to consider the outputs/annotations grouped by input instead of individual runs.
> Maybe that just means that we need to allow Cursor to manipulate the run object... aka make SQL queries.

## Monitor the health of production

> basically setting up a ChatGPT task, or a github action triggered via a CRON that runs claude code

1. (Agent) give me a vibe check on 1% of today's runs based on the following criteria: [...] then post the response on slack
2. (UI) view the experiment
