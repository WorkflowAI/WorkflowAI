# Structured Outputs

## Introduction

(when are structured outputs useful?)

## Supported models

WorkflowAI Advantage:
A key benefit of using the WorkflowAI platform is that structured outputs are supported across all available models. While some providers only support structured outputs on specific models, WorkflowAI ensures you get properly formatted data from any model you choose to use. This means you can reliably extract structured data regardless of which underlying model powers your application.

## How to use

(show code per integration)

TODO: add code for all integrations and WorkflowAI SDK.

### OpenAI (TypeScript)



### OpenAI (Python)

The `openai` Python library offers a highly convenient way to achieve this by directly providing a [Pydantic](https://docs.pydantic.dev/latest/) model definition.

To get structured output using the `openai` Python library with WorkflowAI:

1.  Define your desired output structure as a Pydantic `BaseModel`.
2.  Use the `client.beta.chat.completions.parse()` method (note the `.parse()` instead of `.create()`).
3.  Pass your Pydantic class directly to the `response_format` parameter.
4.  Access the parsed Pydantic object directly from `response.choices[0].message.parsed`.

**Example: Getting Country using a Pydantic Model**

Let's redefine the `get_country` example using a Pydantic model:

```python
from pydantic import BaseModel
# Assuming `openai` client is configured as `client`

class CountryInfo(BaseModel):
    country: str

def get_country(city: str):
    # Use the `.parse()` method for structured output with Pydantic
    completion = client.beta.chat.completions.parse(
      # Use a descriptive agent prefix for organization
      model="country-extractor/gpt-4o",
      messages=[
        {"role": "system", "content": "You are a helpful assistant that extracts geographical information."},
        {"role": "user", "content": f"What is the country of {city}?"}
      ],
      # Pass the Pydantic class directly as the response format
      response_format=CountryInfo
    )
    
    parsed_output: CountryInfo = completion.choices[0].message.parsed
    return parsed_output
```

This approach leverages the `openai` library's integration with Pydantic to abstract away the manual JSON schema definition and response parsing, providing a cleaner developer experience.

{% hint style="info" %}
When using structured output, the prompt does not need to explicitly ask for JSON output, as WorkflowAI automatically handles the formatting. Simply focus on describing the task clearly and let WorkflowAI take care of ensuring the response matches your defined schema.
{% endhint %}

## Description and examples

You can significantly improve the LLM's understanding of the desired output structure by providing `description` and `examples` directly within your `response_model` schema. By using `pydantic.Field`, you can annotate each field with a clear description of its purpose and provide a list of illustrative examples. These descriptions and examples are passed along to the LLM as part of the schema definition, helping it grasp the expected data format and content for each attribute.

Here's an example:

{% tabs %}
{% tab title="Python" %}
```python
from typing import Optional, List
from pydantic import BaseModel, Field

class CalendarEvent(BaseModel):
    title: Optional[str] = Field(
        None, 
        description="The event title/name", 
        examples=["Team Meeting", "Quarterly Review"]
    )
    date: Optional[str] = Field(
        None, 
        description="Date in YYYY-MM-DD format", 
        examples=["2023-05-21", "2023-06-15"]
    )
    start_time: Optional[str] = Field(
        None, 
        description="Start time in 24-hour format", 
        examples=["14:00", "09:30"]
    )
    ...
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript
import { z } from "zod";

const CalendarEvent = z.object({
    title: z.string().optional()
        .describe("The event title/name"),
    date: z.string().optional()
        .describe("Date in YYYY-MM-DD format"),
    start_time: z.string().optional()
        .describe("Start time in 24-hour format"),
    ...
});
```

{% hint style="info" %}
[TODO: check with @guillaq]
Note: While Pydantic supports adding examples directly in field definitions, the OpenAI TypeScript SDK with Zod schemas currently only supports descriptions through the `.describe()` method. Examples cannot be provided in the same way as with Pydantic.
{% endhint %}
{% endtab %}

{% tab title="CURL" %}
[TODO: check syntax with @guillaq]
```bash
curl https://api.workflowai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "event-extractor/gpt-4o",
    "messages": [
      {
        "role": "system",
        "content": "Extract calendar event information from the provided text."
      },
      {
        "role": "user",
        "content": "Extract event details from: Meeting with team tomorrow at 2pm in conference room B to discuss Q4 planning"
      }
    ],
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "CalendarEvent",
        "strict": true,
        "schema": {
          "type": "object",
          "properties": {
            "title": {
              "type": "string",
              "description": "The event title/name",
              "examples": ["Team Meeting", "Quarterly Review"]
            },
            "date": {
              "type": "string",
              "description": "Date in YYYY-MM-DD format",
              "examples": ["2023-05-21", "2023-06-15"]
            },
            "start_time": {
              "type": "string",
              "description": "Start time in 24-hour format",
              "examples": ["14:00", "09:30"]
            }
          }
        }
      }
    }
  }'
```

{% hint style="info" %}
When using CURL or the raw API, you define the schema using JSON Schema format. Field descriptions are provided using the `"description"` property, and examples can be provided using the `"examples"` array.
{% endhint %}
{% endtab %}
{% endtabs %}

By providing these details, you make the task clearer for the LLM, reducing ambiguity and leading to better, more reliable structured data extraction.

## Migrating to Structured Outputs

Here are common examples showing how to migrate from traditional JSON prompting to using structured outputs:

[TODO:
- fix tabs under examples (try with Mintlify)
- add examples for Typescript
- add examples for CURL
- ]

<details>

<summary>Example: Extract meeting details from text</summary>

{% tabs %}
{% tab title="Python" %}
**Before (JSON prompting):**
```python
def extract_meeting_info(text: str):
    completion = client.chat.completions.create(
        model="meeting-extractor/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract meeting information and return as JSON with keys: date, time, attendees (list), location, agenda"},
            {"role": "user", "content": f"Extract meeting details from: {text}"}
        ]
    )
    
    # Manual JSON parsing with error handling
    import json
    try:
        return json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        return None
```

**After (Structured outputs):**
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class MeetingInfo(BaseModel):
    date: str = Field(description="Meeting date in YYYY-MM-DD format")
    time: str = Field(description="Meeting time in HH:MM format (24-hour)")
    attendees: List[str] = Field(description="List of attendee names")
    location: Optional[str] = Field(None, description="Meeting location or 'virtual' for online meetings")
    agenda: Optional[str] = Field(None, description="Meeting agenda or main topics")

def extract_meeting_info(text: str):
    completion = client.beta.chat.completions.parse(
        model="meeting-extractor/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract meeting information from the provided text."},
            {"role": "user", "content": f"Extract meeting details from: {text}"}
        ],
        response_format=MeetingInfo
    )
    
    # Direct access to parsed object
    return completion.choices[0].message.parsed
```
{% endtab %}

{% tab title="TypeScript" %}
**Before (JSON prompting):**
```typescript
async function extractMeetingInfo(text: string) {
    const completion = await client.chat.completions.create({
        model: "meeting-extractor/gpt-4o",
        messages: [
            {role: "system", content: "Extract meeting information and return as JSON with keys: date, time, attendees (list), location, agenda"},
            {role: "user", content: `Extract meeting details from: ${text}`}
        ]
    });
    
    // Manual JSON parsing with error handling
    try {
        return JSON.parse(completion.choices[0].message.content);
    } catch (error) {
        return null;
    }
}
```

**After (Structured outputs):**
```typescript
import { z } from "zod";
import { zodResponseFormat } from "openai/helpers/zod";

const MeetingInfo = z.object({
    date: z.string().describe("Meeting date in YYYY-MM-DD format"),
    time: z.string().describe("Meeting time in HH:MM format (24-hour)"),
    attendees: z.array(z.string()).describe("List of attendee names"),
    location: z.string().optional().describe("Meeting location or 'virtual' for online meetings"),
    agenda: z.string().optional().describe("Meeting agenda or main topics")
});

async function extractMeetingInfo(text: string) {
    const completion = await client.beta.chat.completions.parse({
        model: "meeting-extractor/gpt-4o",
        messages: [
            {role: "system", content: "Extract meeting information from the provided text."},
            {role: "user", content: `Extract meeting details from: ${text}`}
        ],
        response_format: zodResponseFormat(MeetingInfo, "MeetingInfo")
    });
    
    // Direct access to parsed object
    return completion.choices[0].message.parsed;
}
```
{% endtab %}
{% endtabs %}

</details>

<details>

<summary>Example: Product review sentiment analysis</summary>

{% tabs %}
{% tab title="Python" %}
**Before (JSON prompting):**
```python
def analyze_review(review_text: str):
    completion = client.chat.completions.create(
        model="review-analyzer/gpt-4o",
        messages=[
            {"role": "system", "content": "Analyze the product review and return JSON with: rating (1-5), sentiment (positive/neutral/negative), pros (list), cons (list), summary"},
            {"role": "user", "content": f"Analyze this review: {review_text}"}
        ]
    )
    
    import json
    try:
        return json.loads(completion.choices[0].message.content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse response"}
```

**After (Structured outputs):**
```python
from pydantic import BaseModel, Field
from typing import List, Literal

class ProductReview(BaseModel):
    rating: int = Field(description="Overall rating from 1 to 5", ge=1, le=5)
    sentiment: Literal["positive", "neutral", "negative"] = Field(description="Overall sentiment of the review")
    pros: List[str] = Field(description="List of positive aspects mentioned")
    cons: List[str] = Field(description="List of negative aspects mentioned")
    summary: str = Field(description="Brief summary of the review in 1-2 sentences")

def analyze_review(review_text: str):
    completion = client.beta.chat.completions.parse(
        model="review-analyzer/gpt-4o",
        messages=[
            {"role": "system", "content": "Analyze the product review sentiment and key points."},
            {"role": "user", "content": f"Analyze this review: {review_text}"}
        ],
        response_format=ProductReview
    )
    
    return completion.choices[0].message.parsed
```
{% endtab %}

{% tab title="TypeScript" %}
**Before (JSON prompting):**
```typescript
async function analyzeReview(reviewText: string) {
    const completion = await client.chat.completions.create({
        model: "review-analyzer/gpt-4o",
        messages: [
            {role: "system", content: "Analyze the product review and return JSON with: rating (1-5), sentiment (positive/neutral/negative), pros (list), cons (list), summary"},
            {role: "user", content: `Analyze this review: ${reviewText}`}
        ]
    });
    
    try {
        return JSON.parse(completion.choices[0].message.content);
    } catch (error) {
        return {error: "Failed to parse response"};
    }
}
```

**After (Structured outputs):**
```typescript
import { z } from "zod";
import { zodResponseFormat } from "openai/helpers/zod";

const ProductReview = z.object({
    rating: z.number().int().min(1).max(5).describe("Overall rating from 1 to 5"),
    sentiment: z.enum(["positive", "neutral", "negative"]).describe("Overall sentiment of the review"),
    pros: z.array(z.string()).describe("List of positive aspects mentioned"),
    cons: z.array(z.string()).describe("List of negative aspects mentioned"),
    summary: z.string().describe("Brief summary of the review in 1-2 sentences")
});

async function analyzeReview(reviewText: string) {
    const completion = await client.beta.chat.completions.parse({
        model: "review-analyzer/gpt-4o",
        messages: [
            {role: "system", content: "Analyze the product review sentiment and key points."},
            {role: "user", content: `Analyze this review: ${reviewText}`}
        ],
        response_format: zodResponseFormat(ProductReview, "ProductReview")
    });
    
    return completion.choices[0].message.parsed;
}
```
{% endtab %}
{% endtabs %}

</details>

<details>

<summary>Example: Resume/CV information extraction</summary>

{% tabs %}
{% tab title="Python" %}
**Before (JSON prompting):**
```python
def parse_resume(resume_text: str):
    completion = client.chat.completions.create(
        model="resume-parser/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract resume information and return as JSON with: name, email, phone, skills (list), experience (list of objects with company, role, duration), education (list)"},
            {"role": "user", "content": f"Parse this resume: {resume_text}"}
        ]
    )
    
    import json
    try:
        data = json.loads(completion.choices[0].message.content)
        # Additional validation needed
        return data
    except (json.JSONDecodeError, KeyError):
        return None
```

**After (Structured outputs):**
```python
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

class Experience(BaseModel):
    company: str = Field(description="Company name")
    role: str = Field(description="Job title/role")
    duration: str = Field(description="Employment period (e.g., 'Jan 2020 - Dec 2022')")
    description: Optional[str] = Field(None, description="Brief description of responsibilities")

class Education(BaseModel):
    institution: str = Field(description="School/University name")
    degree: str = Field(description="Degree or certification obtained")
    year: Optional[str] = Field(None, description="Graduation year or period")

class ResumeData(BaseModel):
    name: str = Field(description="Full name of the candidate")
    email: Optional[EmailStr] = Field(None, description="Contact email address")
    phone: Optional[str] = Field(None, description="Contact phone number")
    skills: List[str] = Field(description="List of technical and soft skills")
    experience: List[Experience] = Field(description="Work experience entries")
    education: List[Education] = Field(description="Educational background entries")

def parse_resume(resume_text: str):
    completion = client.beta.chat.completions.parse(
        model="resume-parser/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract structured information from the resume."},
            {"role": "user", "content": f"Parse this resume: {resume_text}"}
        ],
        response_format=ResumeData
    )
    
    return completion.choices[0].message.parsed
```
{% endtab %}

{% tab title="TypeScript" %}
**Before (JSON prompting):**
```typescript
async function parseResume(resumeText: string) {
    const completion = await client.chat.completions.create({
        model: "resume-parser/gpt-4o",
        messages: [
            {role: "system", content: "Extract resume information and return as JSON with: name, email, phone, skills (list), experience (list of objects with company, role, duration), education (list)"},
            {role: "user", content: `Parse this resume: ${resumeText}`}
        ]
    });
    
    try {
        const data = JSON.parse(completion.choices[0].message.content);
        // Additional validation needed
        return data;
    } catch (error) {
        return null;
    }
}
```

**After (Structured outputs):**
```typescript
import { z } from "zod";
import { zodResponseFormat } from "openai/helpers/zod";

const Experience = z.object({
    company: z.string().describe("Company name"),
    role: z.string().describe("Job title/role"),
    duration: z.string().describe("Employment period (e.g., 'Jan 2020 - Dec 2022')"),
    description: z.string().optional().describe("Brief description of responsibilities")
});

const Education = z.object({
    institution: z.string().describe("School/University name"),
    degree: z.string().describe("Degree or certification obtained"),
    year: z.string().optional().describe("Graduation year or period")
});

const ResumeData = z.object({
    name: z.string().describe("Full name of the candidate"),
    email: z.string().email().optional().describe("Contact email address"),
    phone: z.string().optional().describe("Contact phone number"),
    skills: z.array(z.string()).describe("List of technical and soft skills"),
    experience: z.array(Experience).describe("Work experience entries"),
    education: z.array(Education).describe("Educational background entries")
});

async function parseResume(resumeText: string) {
    const completion = await client.beta.chat.completions.parse({
        model: "resume-parser/gpt-4o",
        messages: [
            {role: "system", content: "Extract structured information from the resume."},
            {role: "user", content: `Parse this resume: ${resumeText}`}
        ],
        response_format: zodResponseFormat(ResumeData, "ResumeData")
    });
    
    return completion.choices[0].message.parsed;
}
```
{% endtab %}
{% endtabs %}

</details>

<details>

<summary>Example: Recipe parsing</summary>

{% tabs %}
{% tab title="Python" %}
**Before (JSON prompting):**
```python
def parse_recipe(recipe_text: str):
    completion = client.chat.completions.create(
        model="recipe-parser/gpt-4o",
        messages=[
            {"role": "system", "content": "Parse the recipe and return JSON with: title, servings, prep_time, cook_time, ingredients (list with amount and item), instructions (ordered list), tags (list)"},
            {"role": "user", "content": f"Parse this recipe: {recipe_text}"}
        ]
    )
    
    import json
    try:
        recipe_data = json.loads(completion.choices[0].message.content)
        # Manual validation of required fields
        if not all(k in recipe_data for k in ['title', 'ingredients', 'instructions']):
            raise ValueError("Missing required fields")
        return recipe_data
    except (json.JSONDecodeError, ValueError):
        return None
```

**After (Structured outputs):**
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class Ingredient(BaseModel):
    amount: str = Field(description="Quantity (e.g., '2 cups', '1 tbsp')")
    item: str = Field(description="Ingredient name")
    notes: Optional[str] = Field(None, description="Preparation notes (e.g., 'diced', 'room temperature')")

class Recipe(BaseModel):
    title: str = Field(description="Recipe name")
    servings: int = Field(description="Number of servings", ge=1)
    prep_time: Optional[str] = Field(None, description="Preparation time (e.g., '15 minutes')")
    cook_time: Optional[str] = Field(None, description="Cooking time (e.g., '45 minutes')")
    ingredients: List[Ingredient] = Field(description="List of ingredients with amounts")
    instructions: List[str] = Field(description="Step-by-step cooking instructions")
    tags: List[str] = Field(default_factory=list, description="Recipe tags (e.g., 'vegetarian', 'gluten-free')")

def parse_recipe(recipe_text: str):
    completion = client.beta.chat.completions.parse(
        model="recipe-parser/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract recipe information in a structured format."},
            {"role": "user", "content": f"Parse this recipe: {recipe_text}"}
        ],
        response_format=Recipe
    )
    
    return completion.choices[0].message.parsed
```
{% endtab %}

{% tab title="TypeScript" %}
**Before (JSON prompting):**
```typescript
async function parseRecipe(recipeText: string) {
    const completion = await client.chat.completions.create({
        model: "recipe-parser/gpt-4o",
        messages: [
            {role: "system", content: "Parse the recipe and return JSON with: title, servings, prep_time, cook_time, ingredients (list with amount and item), instructions (ordered list), tags (list)"},
            {role: "user", content: `Parse this recipe: ${recipeText}`}
        ]
    });
    
    try {
        const recipeData = JSON.parse(completion.choices[0].message.content);
        // Manual validation of required fields
        if (!['title', 'ingredients', 'instructions'].every(k => k in recipeData)) {
            throw new Error("Missing required fields");
        }
        return recipeData;
    } catch (error) {
        return null;
    }
}
```

**After (Structured outputs):**
```typescript
import { z } from "zod";
import { zodResponseFormat } from "openai/helpers/zod";

const Ingredient = z.object({
    amount: z.string().describe("Quantity (e.g., '2 cups', '1 tbsp')"),
    item: z.string().describe("Ingredient name"),
    notes: z.string().optional().describe("Preparation notes (e.g., 'diced', 'room temperature')")
});

const Recipe = z.object({
    title: z.string().describe("Recipe name"),
    servings: z.number().int().min(1).describe("Number of servings"),
    prep_time: z.string().optional().describe("Preparation time (e.g., '15 minutes')"),
    cook_time: z.string().optional().describe("Cooking time (e.g., '45 minutes')"),
    ingredients: z.array(Ingredient).describe("List of ingredients with amounts"),
    instructions: z.array(z.string()).describe("Step-by-step cooking instructions"),
    tags: z.array(z.string()).default([]).describe("Recipe tags (e.g., 'vegetarian', 'gluten-free')")
});

async function parseRecipe(recipeText: string) {
    const completion = await client.beta.chat.completions.parse({
        model: "recipe-parser/gpt-4o",
        messages: [
            {role: "system", content: "Extract recipe information in a structured format."},
            {role: "user", content: `Parse this recipe: ${recipeText}`}
        ],
        response_format: zodResponseFormat(Recipe, "Recipe")
    });
    
    return completion.choices[0].message.parsed;
}
```
{% endtab %}
{% endtabs %}

</details>

<details>

<summary>Example: Invoice/receipt data extraction</summary>

{% tabs %}
{% tab title="Python" %}
**Before (JSON prompting):**
```python
def extract_invoice_data(invoice_text: str):
    completion = client.chat.completions.create(
        model="invoice-extractor/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract invoice data and return JSON with: invoice_number, date, vendor_name, vendor_address, items (list with description, quantity, unit_price, total), subtotal, tax, total_amount"},
            {"role": "user", "content": f"Extract data from this invoice: {invoice_text}"}
        ]
    )
    
    import json
    try:
        invoice = json.loads(completion.choices[0].message.content)
        # Manual type conversion for numeric fields
        invoice['subtotal'] = float(invoice.get('subtotal', 0))
        invoice['tax'] = float(invoice.get('tax', 0))
        invoice['total_amount'] = float(invoice.get('total_amount', 0))
        return invoice
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
```

**After (Structured outputs):**
```python
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import date

class LineItem(BaseModel):
    description: str = Field(description="Item or service description")
    quantity: float = Field(description="Quantity purchased", gt=0)
    unit_price: Decimal = Field(description="Price per unit")
    total: Decimal = Field(description="Line item total (quantity × unit_price)")

class Invoice(BaseModel):
    invoice_number: str = Field(description="Invoice or receipt number")
    date: date = Field(description="Invoice date")
    vendor_name: str = Field(description="Vendor/seller name")
    vendor_address: Optional[str] = Field(None, description="Vendor address")
    items: List[LineItem] = Field(description="List of line items")
    subtotal: Decimal = Field(description="Subtotal before tax")
    tax: Decimal = Field(description="Tax amount")
    total_amount: Decimal = Field(description="Total amount due")
    currency: str = Field(default="USD", description="Currency code (e.g., USD, EUR)")

def extract_invoice_data(invoice_text: str):
    completion = client.beta.chat.completions.parse(
        model="invoice-extractor/gpt-4o",
        messages=[
            {"role": "system", "content": "Extract structured invoice data from the provided text."},
            {"role": "user", "content": f"Extract data from this invoice: {invoice_text}"}
        ],
        response_format=Invoice
    )
    
    return completion.choices[0].message.parsed
```
{% endtab %}

{% tab title="TypeScript" %}
**Before (JSON prompting):**
```typescript
async function extractInvoiceData(invoiceText: string) {
    const completion = await client.chat.completions.create({
        model: "invoice-extractor/gpt-4o",
        messages: [
            {role: "system", content: "Extract invoice data and return JSON with: invoice_number, date, vendor_name, vendor_address, items (list with description, quantity, unit_price, total), subtotal, tax, total_amount"},
            {role: "user", content: `Extract data from this invoice: ${invoiceText}`}
        ]
    });
    
    try {
        const invoice = JSON.parse(completion.choices[0].message.content);
        // Manual type conversion for numeric fields
        invoice.subtotal = parseFloat(invoice.subtotal || 0);
        invoice.tax = parseFloat(invoice.tax || 0);
        invoice.total_amount = parseFloat(invoice.total_amount || 0);
        return invoice;
    } catch (error) {
        return null;
    }
}
```

**After (Structured outputs):**
```typescript
import { z } from "zod";
import { zodResponseFormat } from "openai/helpers/zod";

const LineItem = z.object({
    description: z.string().describe("Item or service description"),
    quantity: z.number().positive().describe("Quantity purchased"),
    unit_price: z.number().describe("Price per unit"),
    total: z.number().describe("Line item total (quantity × unit_price)")
});

const Invoice = z.object({
    invoice_number: z.string().describe("Invoice or receipt number"),
    date: z.string().describe("Invoice date in YYYY-MM-DD format"),
    vendor_name: z.string().describe("Vendor/seller name"),
    vendor_address: z.string().optional().describe("Vendor address"),
    items: z.array(LineItem).describe("List of line items"),
    subtotal: z.number().describe("Subtotal before tax"),
    tax: z.number().describe("Tax amount"),
    total_amount: z.number().describe("Total amount due"),
    currency: z.string().default("USD").describe("Currency code (e.g., USD, EUR)")
});

async function extractInvoiceData(invoiceText: string) {
    const completion = await client.beta.chat.completions.parse({
        model: "invoice-extractor/gpt-4o",
        messages: [
            {role: "system", content: "Extract structured invoice data from the provided text."},
            {role: "user", content: `Extract data from this invoice: ${invoiceText}`}
        ],
        response_format: zodResponseFormat(Invoice, "Invoice")
    });
    
    return completion.choices[0].message.parsed;
}
```
{% endtab %}
{% endtabs %}

</details>