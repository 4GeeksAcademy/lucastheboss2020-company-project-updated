"""Trusted application-to-agent contracts. Never construct these from chat/model text."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ResourceGrant(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    reference: str=Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9_-]+$')
    owner_subject: str=Field(min_length=1,max_length=100)
    company: str=Field(min_length=1,max_length=100)
    country: Literal['US','ES']
    resource_type: Literal['order','tracking','incident']='order'
    aliases: tuple[str,...]=()

    @model_validator(mode='after')
    def safe_aliases(self):
        import re
        if len(self.aliases)>20 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',a) for a in self.aliases):
            raise ValueError('Invalid resource aliases')
        return self

class AuthenticatedSession(BaseModel):
    """Authenticated server identity plus server-resolved ownership/country grants.
    This object is NOT authentication. A web client/model must never supply it.
    Existing CLI operator files are trusted local integration fixtures, not bearer tokens.
    """
    model_config=ConfigDict(extra='forbid',frozen=True)
    company: str=Field(min_length=1,max_length=100)
    subject: str=Field(min_length=1,max_length=100)
    customer_type: Literal['B2B','B2C','staff']
    country: Literal['US','ES']
    expires_at: float=Field(gt=0)
    resources: tuple[ResourceGrant,...]=()
    active_reference: str | None=None
    permissions: tuple[Literal['incidents:read','incidents:create','incidents:write','inventory:read'],...]=()
    client_name: str | None=Field(default=None,max_length=120)

    @model_validator(mode='after')
    def bounded(self):
        import math
        if not math.isfinite(self.expires_at): raise ValueError('Session expiry must be finite')
        if len(self.resources)>100: raise ValueError('Too many session resources')
        refs=[]
        for grant in self.resources: refs.extend((grant.reference,*grant.aliases))
        if len({r.casefold() for r in refs})!=len(refs): raise ValueError('Ambiguous resource grants')
        if self.active_reference and self.active_reference.casefold() not in {r.casefold() for r in refs}:
            raise ValueError('Active resource is not in session grants')
        return self

@dataclass(frozen=True)
class GuardDecision:
    question: str
    request_id: str
    country: str | None=None
    references: tuple[str,...]=()
    stop: bool=False
    answer: str=''
    notice: str=''
    allow_memory: bool=True

class GuardrailViolation(RuntimeError):
    """Sanitized failure; never contains raw input, tool payloads or credentials."""
