# Contributing

## Guidelines

### Deployments

This project uses GitHub Actions for CI / CD.

- the `main` branch is the central branch that contains the latest version of WorkflowAI. Any merge on main triggers
  a deployment to the staging environment
- any pull request that targets main triggers a quality check of the client and API portions based on
  the changes. The quality checks are required to pass before merging to main.
- Releases (`release/*`) and hotfix (`hotfix/*`) trigger deployments to the preview environment
- Deployments to the production environment are triggered by versioned tags.

### Branch flow

#### Feature or fix

A traditional feature or fix starts by creating a branch from `main` and results in a pull request on the `main` branch.
By convention, feature branch names should start with the name of the person creating the branch.

#### Release process

Releases are the process of deploying the code currently living in the staging env to production. The flow
starts with the creation of the `release/<release-date>` branch which triggers a deployment to the preview environment. A
PR from the release branch into main should be created as well.
This allows `main` to continue changing independently while the release is being QAed. Any fix for the release
should be a pull request into the release branch.

When the release is ready, the appropriate tags and GitHub releases should be created from the release branch to
trigger deployments to the production environment. Once everything is OK, the branch should be merged to `main`.

#### Hotfix process

A hotfix allows fixing bugs in production without having to push changes to the development environment first.
A hotfix branch should be created from the latest tag and a PR targeting `main` should be created. The flow is then the
same as the release process.

### Adding new models

#### Model enum

The [Model enum](./api/core/domain/models/models.py) contains the list of all models that were ever supported by WorkflowAI.

- never remove a model from the Model enum
- a model ID should always be versioned when possible, meaning that the model ID should include the version number when available e-g `gpt-4.1-2025-04-14`
- the model ID should match the provider's model ID when possible

#### Model data

The [ModelData](./api/core/domain/models/model_data.py) class contains metadata about a model, including the display name, icon URL, etc. It also allows deprecating a model by providing a replacement model.

The actual data is built by `_raw_model_data` in the [model_data_mapping.py](./api/core/domain/models/model_data_mapping.py) file. Every model in the Model enum should have an associated ModelData object.

When adding a new model, you must provide:

- `display_name`: Human-readable name for the model
- `icon_url`: URL to the model's icon (typically the provider's logo)
- `max_tokens_data`: Maximum token limits for input and output
- `release_date`: When the model was released
- `quality_data`: Performance metrics (MMLU, GPQA scores, etc.)
- `speed_data`: Speed index of the model
- `provider_name`: Name of the provider
- `supports_*` flags: What capabilities the model supports (JSON mode, images, etc.)
- `fallback`: Optional fallback configuration for error handling

When deprecating a model, make sure to replace every case where the model is used in the replacement model. We do not allow replacement models to be deprecated. Only deprecate models when either:

- the model will no longer be supported by the provider in the near future
- the model has a clear replacement model and using the original model is not recommended

##### Computing model speed index

To compute the speed index of a model, you can run a pretty lenghty generation on the new model and measure the time it takes.

Then you can feed the model speed_data with the metadata (output tokens count and duration) from the run:


Ex:

```python
speed_data=SpeedData(
    index=SpeedIndex.from_experiment(output_tokens=2252, duration_seconds=18),
)
```

Example script to run a translation on a model:

```python
from typing import Optional

import openai

client = openai.OpenAI(
    api_key="INSERT_API_KEY_HERE",
    base_url="https://run.workflowai.com/v1",
)


def translate_to_french(
    text: str, context: Optional[str] = None, tone: Optional[str] = None
):
    system_prompt = """You are an expert French translator with deep knowledge of French language, culture, and nuances. Your task is to translate text to French while preserving meaning, tone, and cultural context.

For each translation, provide:

**Translated Text**: The French translation that accurately conveys the meaning and tone of the original text.

Consider:
- Regional variations (France vs. Quebec vs. other French-speaking regions)
- Formal vs. informal register
- Cultural context and idioms
- Technical terminology when applicable
- Tone and style preservation
"""

    user_prompt = """
    Text to translate: {{text}}

    Please provide a high-quality French translation with appropriate cultural and linguistic considerations.
    """

    response = client.chat.completions.create(
        model="gemini-2.0-flash-001",  # pick the model here
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        metadata={
            "agent_id": "french-translation",
        },
        extra_body={
            "input": {
                "text": text,
            },
        },
    )

    return response.choices[0].message.content


# Example usage and testing
if __name__ == "__main__":
    text = """Geoffrey Everest Hinton (born 1947) is a British-Canadian computer scientist, cognitive scientist, and cognitive psychologist known for his work on artificial neural networks, which earned him the title "the Godfather of AI".[9]

Hinton is University Professor Emeritus at the University of Toronto. From 2013 to 2023, he divided his time working for Google (Google Brain) and the University of Toronto before publicly announcing his departure from Google in May 2023, citing concerns about the many risks of artificial intelligence (AI) technology.[10][11] In 2017, he co-founded and became the chief scientific advisor of the Vector Institute in Toronto.[12][13]

With David Rumelhart and Ronald J. Williams, Hinton was co-author of a highly cited paper published in 1986 that popularised the backpropagation algorithm for training multi-layer neural networks,[14] although they were not the first to propose the approach.[15] Hinton is viewed as a leading figure in the deep learning community.[21] The image-recognition milestone of the AlexNet designed in collaboration with his students Alex Krizhevsky[22] and Ilya Sutskever for the ImageNet challenge 2012[8] was a breakthrough in the field of computer vision.[23]

Hinton received the 2018 Turing Award, often referred to as the "Nobel Prize of Computing", together with Yoshua Bengio and Yann LeCun for their work on deep learning.[24] They are sometimes referred to as the "Godfathers of Deep Learning"[25][26] and have continued to give public talks together.[27][28] He was also awarded, along with John Hopfield, the 2024 Nobel Prize in Physics for foundational discoveries and inventions that enable machine learning with artificial neural networks.[29][30]

In May 2023, Hinton announced his resignation from Google to be able to "freely speak out about the risks of A.I."[31] He has voiced concerns about deliberate misuse by malicious actors, technological unemployment, and existential risk from artificial general intelligence.[32] He noted that establishing safety guidelines will require cooperation among those competing in use of AI in order to avoid the worst outcomes.[33] After receiving the Nobel Prize, he called for urgent research into AI safety to figure out how to control AI systems smarter than humans.[34][35][36]

Education
Hinton was born on 6 December 1947[37] in Wimbledon, England, and was educated at Clifton College in Bristol.[38] In 1967, he enrolled as an undergraduate student at King's College, Cambridge, and after repeatedly switching between different fields, like natural sciences, history of art, and philosophy, he eventually graduated with a Bachelor of Arts degree in experimental psychology at the University of Cambridge in 1970.[37][39] He spent a year apprenticing carpentry before returning to academic studies.[40] From 1972 to 1975, he continued his study at the University of Edinburgh, where he was awarded a PhD in artificial intelligence in 1978 for research supervised by Christopher Longuet-Higgins, who favored the symbolic AI approach over the neural network approach.[39][41][42][40]

Career and research
After his PhD, Hinton initially worked at the University of Sussex and at the MRC Applied Psychology Unit. After having difficulty getting funding in Britain,[40] he worked in the US at the University of California, San Diego and Carnegie Mellon University.[37] He was the founding director of the Gatsby Charitable Foundation Computational Neuroscience Unit at University College London.[37] He is currently[43] University Professor Emeritus in the computer science department at the University of Toronto, where he has been affiliated since 1987.[44]

Upon arrival in Canada, Geoffrey Hinton was appointed at the Canadian Institute for Advanced Research (CIFAR) in 1987 as a Fellow in CIFAR's first research program, Artificial Intelligence, Robotics & Society.[45] In 2004, Hinton and collaborators successfully proposed the launch of a new program at CIFAR, "Neural Computation and Adaptive Perception"[46] (NCAP), which today is named "Learning in Machines & Brains". Hinton would go on to lead NCAP for ten years.[47] Among the members of the program are Yoshua Bengio and Yann LeCun, with whom Hinton would go on to win the ACM A.M. Turing Award in 2018.[48] All three Turing winners continue to be members of the CIFAR Learning in Machines & Brains program.[49]

Hinton taught a free online course on Neural Networks on the education platform Coursera in 2012.[50] He co-founded DNNresearch Inc. in 2012 with his two graduate students Alex Krizhevsky and Ilya Sutskever at the University of Toronto’s department of computer science. In March 2013, Google acquired DNNresearch Inc. for $44 million, and Hinton planned to "divide his time between his university research and his work at Google".[51][52][53]

Hinton's research concerns ways of using neural networks for machine learning, memory, perception, and symbol processing. He has written or co-written more than 200 peer-reviewed publications.[1][54]

While Hinton was a postdoc at UC San Diego, David E. Rumelhart and Hinton and Ronald J. Williams applied the backpropagation algorithm to multi-layer neural networks. Their experiments showed that such networks can learn useful internal representations of data.[14] In a 2018 interview,[55] Hinton said that "David E. Rumelhart came up with the basic idea of backpropagation, so it's his invention". Although this work was important in popularising backpropagation, it was not the first to suggest the approach.[15] Reverse-mode automatic differentiation, of which backpropagation is a special case, was proposed by Seppo Linnainmaa in 1970, and Paul Werbos proposed to use it to train neural networks in 1974.[15]

In 1985, Hinton co-invented Boltzmann machines with David Ackley and Terry Sejnowski.[56] His other contributions to neural network research include distributed representations, time delay neural network, mixtures of experts, Helmholtz machines and product of experts.[57] An accessible introduction to Geoffrey Hinton's research can be found in his articles in Scientific American in September 1992 and October 1993.[58] In 2007, Hinton coauthored an unsupervised learning paper titled Unsupervised learning of image transformations.[59] In 2008, he developed the visualization method t-SNE with Laurens van der Maaten.[60][61]

In October and November 2017, Hinton published two open access research papers on the theme of capsule neural networks,[62][63] which, according to Hinton, are "finally something that works well".[64]

At the 2022 Conference on Neural Information Processing Systems (NeurIPS), Hinton introduced a new learning algorithm for neural networks that he calls the "Forward-Forward" algorithm. The idea of the new algorithm is to replace the traditional forward-backward passes of backpropagation with two forward passes, one with positive (i.e. real) data and the other with negative data that could be generated solely by the network.[65][66]

In May 2023, Hinton publicly announced his resignation from Google. He explained his decision by saying that he wanted to "freely speak out about the risks of A.I." and added that a part of him now regrets his life's work.[10][31]

Notable former PhD students and postdoctoral researchers from his group include Peter Dayan,[67] Sam Roweis,[67] Max Welling,[67] Richard Zemel,[41][2] Brendan Frey,[3] Radford M. Neal,[4] Yee Whye Teh,[5] Ruslan Salakhutdinov,[6] Ilya Sutskever,[7] Yann LeCun,[68] Alex Graves,[67] Zoubin Ghahramani,[67] and Peter Fitzhugh Brown.[69]"""

    print(translate_to_french(text))

```

#### Model provider data

The [ModelProviderData](./api/core/domain/models/model_provider_data.py) class contains pricing information per provider per model. If a model is supported by a provider, then it must have a ModelProviderData object.

The provider data is configured in [model_provider_data_mapping.py](./api/core/domain/models/model_provider_data_mapping.py). Each provider has its own dictionary mapping models to their provider data.

When adding a new model, you must add pricing data for each provider that supports it, including:

- `text_price`: Cost per token for input/output
- `image_price`: Cost per image (if applicable)
- `audio_price`: Cost per audio input (if applicable)
- `lifecycle_data`: Sunset dates and replacement models (if applicable)

When deprecating a model, remove its model provider data as well.

When explicitly asked to make a model a "default" model, meaning that it will be displayed by default by the frontend:

- set the `is_default` flag to `True` in the model provider data
- make sure the model places high in the Model enum since the Model enum gives the default order of models.
- add the model to its "usual" position in the enum but comment it out to enhance readability.
- it likely replaces another "default" model, so remove it from the top of the enum and uncomment the corresponding line in its "usual" position.

#### Checking tests

All the tests in the [domain models directory](./api/core/domain/models) should be executed and pass

```bash
pytest api/core/domain/models
```

### Documentation

#### Endpoints

Endpoints or fields that are exposed to the public should be properly documented:

- each endpoint function should be documented with a `docstring`. See the [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/#summary-and-description) for more details.
- a `docstring` should be added to each pydantic model used in a response. The docstring should describe the model and its fields.
- a `description` should be added to each field in the response

```python
class Item(BaseModel):
    """
    The docstring that describes the Object itself
    """
    id: int = Field(
        description="A description of the field",
    )

@router.get("/items")
async def get_items() -> list[Item]:
    """
    The description of the endpoint
    """
    ...
```

##### Excluding certain fields or endpoints for the documentation

Sometimes, certain fields or endpoints should be excluded from the public documentation, because they are internal or not meant to be used by the end user.

- excluding a field should be done with the `SkipJsonSchema` [annotation](https://docs.pydantic.dev/latest/api/json_schema/#pydantic.json_schema.SkipJsonSchema) imported from [`api.routers._common`](api/api/routers/_common.py). Our local implementation wraps the Pydantic annotation to only hide the fields in production.
- excluding an endpoint should be done with the `PRIVATE_KWARGS` variable imported from [`api.routers._common`](api/api/routers/_common.py).

> Do NOT use `Field(exclude=True)` as it excludes the field from being processed by Pydantic and not by the documentation generation.

> Documentation will only be hidden in production. We need full documentation in Dev to allow code generation.

```python
from api.routers._common import PRIVATE_KWARGS, SkipJsonSchema

class Item(BaseModel):
    id: SkipJsonSchema[int] = Field(
        description="A field that will not be displayed in the production documentation.",
    )

@router.get("/items", **PRIVATE_KWARGS)
async def get_items():
    """
    A route that will not be displayed in the production documentation.
    """
    ...
```

