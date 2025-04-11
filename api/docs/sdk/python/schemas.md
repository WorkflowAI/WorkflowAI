# Schemas

List of common schemas.

{% hint style="info" %}
Read first about schemas in the [`@workflowai.agent`](/docs/sdk/python/agent.md#schema-input-output) section.
{% endhint %}

## Chatbot

A chatbot is represented by a back-and-forth conversation between a user and an assistant.

```python
class ChatbotInput(BaseModel):
    user_message: str

class ChatbotOutput(BaseModel):
    assistant_message: str
```

{% hint style="info" %}
Read more about chatbots in the [`@workflowai.agent`](/docs/sdk/python/agent.md#reply-to-a-run) `reply` method section.
{% endhint %}

## PII Extraction

PII extraction is the process of identifying and extracting specific entities from a text.

```python
class PIIType(str, Enum):
    """Categories of Personal Identifiable Information."""
    NAME = "NAME"  # Full names, first names, last names
    EMAIL = "EMAIL"  # Email addresses
    PHONE = "PHONE"  # Phone numbers, fax numbers
    ADDRESS = "ADDRESS"  # Physical addresses, postal codes
    SSN = "SSN"  # Social Security Numbers, National IDs
    DOB = "DOB"  # Date of birth, age
    FINANCIAL = "FINANCIAL"  # Credit card numbers, bank accounts
    LICENSE = "LICENSE"  # Driver's license, professional licenses
    URL = "URL"  # Personal URLs, social media profiles
    OTHER = "OTHER"  # Other types of PII not covered above


class PIIExtraction(BaseModel):
    """Represents an extracted piece of PII with its type."""
    text: str = Field(description="The extracted PII text")
    type: PIIType = Field(description="The category of PII")
    start_index: int = Field(description="Starting position in the original text")
    end_index: int = Field(description="Ending position in the original text")


class PIIInput(BaseModel):
    """Input model for PII extraction."""
    text: str = Field(description="The text to analyze for PII")


class PIIOutput(BaseModel):
    """Output model containing redacted text and extracted PII."""
    redacted_text: str = Field(
        description="The original text with all PII replaced by [REDACTED]",
        examples=[
            "Hi, I'm [REDACTED]. You can reach me at [REDACTED] or call [REDACTED]. "
            "My SSN is [REDACTED] and I live at [REDACTED].",
        ],
    )
    extracted_pii: list[PIIExtraction] = Field(
        description="List of extracted PII items with their types and positions",
        examples=[
            [
                {"text": "John Doe", "type": "NAME", "start_index": 8, "end_index": 16},
                {"text": "john.doe@email.com", "type": "EMAIL", "start_index": 30, "end_index": 47},
                {"text": "555-0123", "type": "PHONE", "start_index": 57, "end_index": 65},
            ],
        ],
    )
```

## Extract positive and negative points from transcript

```python
class FeedbackInput(BaseModel):
    """Input for analyzing a customer feedback call."""
    transcript: str = Field(description="The full transcript of the customer feedback call.")
    call_date: date = Field(description="The date when the call took place.")

# Model representing a single feedback point with supporting evidence
class FeedbackPoint(BaseModel):
    """A specific feedback point with its supporting quote."""
    point: str = Field(description="The main point or insight from the feedback.")
    quote: str = Field(description="The exact quote from the transcript supporting this point.")
    timestamp: str = Field(description="The timestamp or context of when this was mentioned in the call.")

# Model representing the structured analysis of the customer feedback call
class FeedbackOutput(BaseModel):
    """Structured analysis of the customer feedback call."""
    positive_points: list[FeedbackPoint] = Field(
        default_factory=list,
        description="List of positive feedback points, each with a supporting quote."
    )
    negative_points: list[FeedbackPoint] = Field(
        default_factory=list,
        description="List of negative feedback points, each with a supporting quote."
    )
```

## Image

{% hint style="info" %}
Read about image schemas in the [Multimodality](/docs/sdk/python/multimodality.md#images) section.
{% endhint %}

```python
class ImageInput(BaseModel):
    image: Image = Field(description="The image to analyze")


class ImageOutput(BaseModel):
    city: str = Field(default="", description="Name of the city shown in the image")
    country: str = Field(default="", description="Name of the country where the city is located")
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence level in the identification (0-1)",
    )
```

## Audio

{% hint style="info" %}
Read about audio schemas in the [Multimodality](/docs/sdk/python/multimodality.md#audio) section.
{% endhint %}

```python
class AudioInput(BaseModel):
    """Input containing the audio file to analyze."""
    audio: Audio = Field(
        description="The audio recording to analyze for spam/robocall detection",
    )


class SpamIndicator(BaseModel):
    """A specific indicator that suggests the call might be spam."""
    description: str = Field(
        description="Description of the spam indicator found in the audio",
        examples=[
            "Uses urgency to pressure the listener",
            "Mentions winning a prize without entering a contest",
            "Automated/robotic voice detected",
        ],
    )
    quote: str = Field(
        description="The exact quote or timestamp where this indicator appears",
        examples=[
            "'You must act now before it's too late'",
            "'You've been selected as our prize winner'",
            "0:05-0:15 - Synthetic voice pattern detected",
        ],
    )


class AudioClassification(BaseModel):
    """Output containing the spam classification results."""
    is_spam: bool = Field(
        description="Whether the audio is classified as spam/robocall",
    )
    confidence_score: float = Field(
        description="Confidence score for the classification (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    spam_indicators: list[SpamIndicator] = Field(
        default_factory=list,
        description="List of specific indicators that suggest this is spam",
    )
    reasoning: str = Field(
        description="Detailed explanation of why this was classified as spam or legitimate",
    )
```