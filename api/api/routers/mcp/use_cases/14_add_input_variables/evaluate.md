The user message must be changed from the initial state:

Additional 'email_title' and 'email_sender' variables must be added to the user message (exact naming does not matter)

Ex:
```json
{
    "role": "user",
    "content": "Please prioritize this email:\n\nTitle: {{email_title}}\nSender: {{email_sender}}\n\nBody: {{email_content}}",
}
```


The 'prioritize_email' function must be updated to accept new parameters too.

Ex:
```python
def prioritize_email(email_title: str, email_sender: str, email_content: str):
    ...
```