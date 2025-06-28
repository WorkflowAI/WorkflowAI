## Scenario 2: Optimize Agent Performance with Faster Models

### initial state:

```python
import openai

client = openai.OpenAI(api_key="sk-proj-1234567890")

prompt = """
<instructions> Analyze the provided conversation transcript to determine if it indicates a potential scam. Follow these steps:
Carefully examine the transcript.
Identify common scam indicators such as:
Requests for personal or financial information.
Promises of unrealistic rewards or gains.
Pressure to act quickly or threats of negative consequences.
Unusual or unsolicited payment requests.
Inconsistencies or vague details in the story.
Offers to help with financial issues without a valid reason.
Presence of unsolicited messages, especially those containing links or attachments.
Use of shortened URLs or suspicious links.
Determine the role of each participant to accurately identify the user exhibiting scam behavior.
Determine if the conversation is a scam:
If clear scam indicators are present, set is_scam to 'YES'.
Else if some suspicious elements are present, the transcript is long enough and you have enough context but not enough to confirm, set is_scam to 'UNSURE'.
Else if no scam indicators are found or more context is needed to determine if this is a scam or the transcript is too short to make a definitive determination if this is a scam, set is_scam to 'NO'.
Provide a concise reason explaining your determination, highlighting specific elements from the transcript that support your conclusion.
If you determine the conversation is a scam or potentially a scam, include the author_id of the user identified as the scammer in the scamer_id field.
Format the output with 'is_scam', 'reason', and 'scamer_id' fields. If the conversation is definitely not a scam, set 'scamer_id' to an empty string.
Ensure that the 'scamer_id' accurately corresponds to the "speakerId" field of the user exhibiting scam characteristics based on the transcript.
Example:
{
  "is_scam": "YES",
  "reason": "The message is unsolicited, contains a shortened link, and mentions a rewards credit with an urgent expiration date, which are common phishing tactics.",
  "scamer_id": "usr_1M3TB5BZ7D12X8KKBXT08HWEB4"
}
</instructions>
Input will be provided in the user message using a JSON following the schema:
{
  "type": "object",
  "properties": {
    "transcript": {
      "description": "The transcript of the conversation to be checked for scams",
      "type": "string"
    }
  }
}
Return a single JSON object enforcing the following schema:
{
  "type": "object",
  "properties": {
    "is_scam": {
      "description": "Indicates whether the conversation is a scam. Set to 'YES' if clear scam indicators are present and participants do not have a known relationship, 'NO' if no scam indicators are found, the transcript is too short, or participants have a known relationship, and 'UNSURE' if there are multiple suspicious elements but not enough to confirm.",
      "enum": [
        "YES",
        "NO",
        "UNSURE"
      ],
      "type": "string"
    },
    "reason": {
      "description": "The explanation for why the conversation is identified as a scam or not, highlighting specific elements from the transcript that support the conclusion, including the relationship between participants.",
      "type": "string",
      "examples": [
        "The transcript shows an unsolicited invitation to a webinar masterclass from a participant who does not have a prior relationship with the other party.",
        "Participants are known to each other and there are no clear scam indicators present.",
        "Multiple suspicious elements are present, but the relationship between participants makes it inconclusive."
      ]
    },
    "scamer_id": {
      "description": "The `author_id` of the user identified as the scammer. If `is_scam` is `'UNSURE'`, still include the `scammer_id`.",
      "examples": [
        "usr_QQTA93SZAH6XXFYK0E8190KA6M"
      ],
      "type": "string"
    }
  }
}
"""

user_input = """
{
  "transcript": "[{\"speakerId\":\"usr_WG87GX2W5H54N3E3KBQ32E9FPG\",\"text\":\"About:\\nDesoto Door is a local, family-owned company specializing in residential and commercial garage door services, including repair, installation, and maintenance. Established in 2009, the company is dedicated to providing high-quality, customizable garage door solutions.\\n\\nServices:\\n- Garage Door Installation: Professional installation of new garage doors tailored to customer preferences and architectural styles.\\n- Garage Door Repair: Expert repair services for garage doors, addressing issues such as jammed doors, spring, roller, and track repairs.\\n- Garage Door Opener Repair: Specialized repair services for garage door openers, ensuring smooth and reliable operation.\\n- Emergency Garage Door Services: 24/7 emergency repair services for urgent garage door issues.\\n- Gate Opener Installation and Repair: Installation and maintenance of automated gate openers with advanced access control technology.\\n\\nProducts:\\n- Residential Garage Doors: Offering a variety of styles including carriage-house, raised-panel, and modern designs with overhead operation. Available in multiple colors, finishes, and materials to enhance home aesthetics.\\n- Commercial Overhead Doors: Providing energy-efficient and durable overhead doors for commercial spaces, including sectional and rolling steel doors designed for safety and efficiency.\\n\\nPolicies:\\n- Repairs: Repair services are provided by certified technicians with a focus on quality and customer satisfaction.\\n\\nBusiness Hours:\\n- Mon - Friday 8-4\"}]"
}
"""

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": user_input
        }
    ]
)

print(response.choices[0].message.content)
```

### goal:

```
- this AI agent is too slow, i want to use a faster model.
- make sure the faster model give similar results than the current model.
- compare the faster models with the current model.
```

### what is required:

- create API keys
- migrate to WorkflowAI platform
- compare model performance (speed, cost, quality)
- test agent with faster models
- evaluate output consistency between models
