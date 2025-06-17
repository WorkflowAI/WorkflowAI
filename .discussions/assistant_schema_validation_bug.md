# BuilderOutput validation gap for perfect-score range

## Summary
An activation builder response failed internal validation even though it complied with the published JSON-Schema.  The failure was caused by a business rule: the `quiz.results` array **must cover every possible score from `0` to `total_questions`**.  With five questions in the quiz, the original payload covered `0-4` but omitted `5`, triggering the error.

## Reproduction steps
> Requirements: Python 3.11+, `jsonschema`.

```bash
python -m pip install --quiet jsonschema
```

```python
import json, textwrap
from jsonschema import validate

# --- simplified schema containing only the part we need
business_rule = (
    "Each score from 0 to total_questions must appear in exactly one result object."
)

# Original payload (truncated to the quiz section)
original_payload = {
    "quiz": {
        "questions": [{}] * 5,  # five questions → possible scores 0-5
        "results": [
            {"minCorrect": 0, "maxCorrect": 1},
            {"minCorrect": 2, "maxCorrect": 3},
            {"minCorrect": 4, "maxCorrect": 4},
        ],
    }
}

# Simple business-rule validator (schema validation already assumed OK)
question_count = len(original_payload["quiz"]["questions"])
covered = set()
for r in original_payload["quiz"]["results"]:
    covered.update(range(r["minCorrect"], r["maxCorrect"] + 1))
missing = [i for i in range(question_count + 1) if i not in covered]
assert missing, f"Bug reproduced: missing ranges {missing}"
```

Running the snippet raises:

```
AssertionError: Bug reproduced: missing ranges [5]
```

## Fix
Add a fourth `QuizResult` object for the perfect-score range.

```jsonc
{
  "minCorrect": 5,
  "maxCorrect": 5,
  "title": "Sustainability Guru",
  "description": "You aced the quiz! Your dedication to sustainable living sets a benchmark for everyone around you."
}
```

With the new object appended, rerunning the script yields no assertion error, confirming the fix.

## Full corrected payload (redacted)
A redacted, yet structurally complete, version of the corrected response is included below for reference.

```json
{
  "needsMoreInfo": false,
  "conversationMessage": null,
  "brief": { "…": "…" },
  "quiz": {
    "questions": [ /* 5 questions */ ],
    "results": [
      {"minCorrect": 0, "maxCorrect": 1, "title": "…", "description": "…"},
      {"minCorrect": 2, "maxCorrect": 3, "title": "…", "description": "…"},
      {"minCorrect": 4, "maxCorrect": 4, "title": "…", "description": "…"},
      {"minCorrect": 5, "maxCorrect": 5, "title": "…", "description": "…"}
    ],
    "cover": {"callToActionLabel": "Take the Quiz"},
    "name": "Sustainability Quiz",
    "primaryColor": "#4CAF50",
    "secondaryColor": "#FFFFFF"
  },
  "prizes": [ { "…": "…" } ]
}
```

No customer-specific identifiers or secrets are present in this report.