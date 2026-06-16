from .cloudflare import create_email_rules
from .gptmail import create_email_rules as create_gptmail
from .gptmail import get_magic_link


class mailCloud:
    def __init__(self) -> None:
        pass
    def createEmailRules(self, mailName):
        return create_email_rules(mailName)


class gptMail:
    def __init__(self) -> None:
        pass
    def createEmailRules(self, mailName):
        return create_gptmail(mailName)


class gptMailCode:
    """Replace QQMail — polls gptmail API for Claude magic link instead of IMAP."""
    def __init__(self) -> None:
        pass
    def getUserTo(self, email, password=None):
        return get_magic_link(email)