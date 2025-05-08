from datetime import datetime

from pydantic import BaseModel


class HelpScoutEmail(BaseModel):
    conversation_id: int
    from_email: str
    customer_email: str
    cc_emails: list[str]
    bcc_emails: list[str]

    subject: str
    body: str
    sent_at: datetime
