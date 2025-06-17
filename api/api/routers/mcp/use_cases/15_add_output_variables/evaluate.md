The 'EmailPriority' model must be updated to include the new priority level.

Ex:
```python
class EmailPriority(BaseModel):
    reasoning: str = Field(
        description="Brief explanation of why this priority was assigned",
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Priority level based on urgency and importance",
    )
    priority_int: int = Field(
        description="Priority level based on urgency and importance (1 to 10)",
        ge=1,
        le=10,
    )
```
