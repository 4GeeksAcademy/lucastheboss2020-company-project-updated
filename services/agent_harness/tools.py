"""Wrap discovered MCP tools before the model sees or executes them."""
from __future__ import annotations
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator, field_validator
from langchain_core.tools import StructuredTool
from uuid import UUID
from services.incidents.manager_models import IncidentBranch,IncidentCategory,IncidentOrigin,IncidentStatus
from services.schemas import Category as InventoryCategory
from .models import GuardrailViolation
from .policy import _INJECTION, _LOCATION, _COMMERCIAL, _SECRET, normalize

class GetIncidentArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    incident_id: str=Field(min_length=1,max_length=120)
    @field_validator('incident_id')
    @classmethod
    def valid_uuid(cls,value): return str(UUID(value))
class UpdateIncidentArgs(GetIncidentArgs):
    status: IncidentStatus
class CreateIncidentArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(min_length=3,max_length=200)
    description: str=Field(min_length=10,max_length=2000)
    category: IncidentCategory
    origin: IncidentOrigin
    branch: IncidentBranch
class InventoryArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: str=Field(default='',max_length=500)
    sku: str | None=Field(default=None,max_length=120)
    client_name: str | None=Field(default=None,max_length=120)
    category: InventoryCategory | None=None
    warehouse: Literal['LA','ZGZ'] | None=None
    limit: int=Field(default=20,ge=1,le=100)
    operation: Literal['read']='read'

class ToolEnvelope(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    ok: bool
    data: dict | list[dict] | None=None
    error: dict | None=None
    count: int | None=None
    read_only: bool | None=None
    @model_validator(mode='after')
    def consistent(self):
        if self.ok and self.data is None or not self.ok and self.error is None:
            raise ValueError('Inconsistent MCP result envelope')
        return self

_TOOL_SPECS={
    'get_incident':(GetIncidentArgs,'Get a single incident linked to the authenticated session.'),
    'update_incident_status':(UpdateIncidentArgs,'Update an authorized incident status; explicit write permission and request required.'),
    'create_incident':(CreateIncidentArgs,'Create a TrackFlow incident only with explicit permission and an explicit user request.'),
    'query_inventory':(InventoryArgs,'Read inventory using authenticated staff or B2B client scope. Inventory is read-only.'),
}

_NEGATED_OPERATION=re.compile(r"\b(?:do not|don['’]?t|never|avoid|cancel|stop)\b.{0,60}\b(?:create|open|file|raise|update|change|mark|resolve|close|get|fetch|read|show|query|list)\b",re.I)

def explicit_write_intent(question,name):
    n=normalize(question)
    if _NEGATED_OPERATION.search(n) or not re.search(r'\b(incident|ticket|incidencia)\b',n): return False
    prefix=r'^(?:(?:please|kindly)\s+)?(?:(?:can|could|would)\s+you\s+(?:please\s+)?)?'
    if name=='create_incident':
        return bool(re.search(prefix+r'(?:create|file|raise|crear|registrar|open\s+(?:a|an|new))\b',n))
    match=re.search(prefix+r'(update|change|set|mark|resolve|close|actualizar)\b',n)
    return bool(match) and (match[1] in {'resolve','close'} or bool(re.search(r'\b(status|state|estado)\b',n)) or match[1]=='mark' and bool(re.search(r'\b(open|resolved|discarded|in progress)\b',n)))

def authorize_arguments(harness,name,arguments,ctx):
    if name not in _TOOL_SPECS:
        harness.record('security','unknown_tool','block',ctx); raise GuardrailViolation('Tool is outside the fixed allowlist')
    schema=_TOOL_SPECS[name][0]
    try: args=schema.model_validate(arguments).model_dump(mode='json')
    except (ValidationError,TypeError):
        harness.record('structural','tool_arguments','block',ctx); raise GuardrailViolation('Invalid tool arguments') from None
    raw=json.dumps(args,ensure_ascii=False)
    if _INJECTION.search(normalize(raw)) or _SECRET.search(raw):
        harness.record('security','tool_argument_injection','block',ctx); raise GuardrailViolation('Unsafe tool arguments')
    if _LOCATION.search(raw) or _COMMERCIAL.search(raw):
        harness.record('content','tool_argument_sensitive','block',ctx); raise GuardrailViolation('Restricted tool arguments')
    if _NEGATED_OPERATION.search(normalize(ctx.question)):
        harness.record('content','negated_operation','block',ctx);raise GuardrailViolation('The user declined this operation')
    session=harness.session
    permissions={'get_incident':'incidents:read','create_incident':'incidents:create','update_incident_status':'incidents:write','query_inventory':'inventory:read'}
    import time
    if not session or session.expires_at<=time.time() or permissions[name] not in session.permissions:
        harness.record('content','tool_authorization','block',ctx); raise GuardrailViolation('Authenticated tool permission is required')
    if name in {'get_incident','update_incident_status'}:
        grant=harness.grant(args['incident_id'])
        requested=[harness.grant(ref) for ref in ctx.references]
        if not grant or not any(g and g==grant for g in requested):
            harness.record('content','tool_resource_authorization','block',ctx); raise GuardrailViolation('Resource is not authorized for this request')
    if name in {'create_incident','update_incident_status'}:
        if not explicit_write_intent(ctx.question,name):
            harness.record('content','unsolicited_write','block',ctx); raise GuardrailViolation('No explicit write request')
    if name=='create_incident':
        branch_country=None if args['branch']=='central' else 'US' if args['branch'].startswith('la_') else 'ES'
        if not ctx.country or branch_country is not None and branch_country!=ctx.country:
            harness.record('content','tool_country','block',ctx); raise GuardrailViolation('Tool country does not match trusted context')
    if name=='query_inventory':
        if session.customer_type=='B2C' or session.customer_type=='B2B' and not session.client_name:
            harness.record('content','inventory_client_scope','block',ctx); raise GuardrailViolation('Inventory client scope is unavailable')
        if session.customer_type=='B2B': args['client_name']=session.client_name
        if args['warehouse'] and ('US' if args['warehouse']=='LA' else 'ES')!=ctx.country:
            harness.record('content','tool_country','block',ctx); raise GuardrailViolation('Inventory country does not match trusted context')
        if ctx.country: args['warehouse']='LA' if ctx.country=='US' else 'ZGZ'
    return args

def secure_tools(discovered,harness,ctx,*,on_result=None):
    result=[]
    for original in discovered:
        name=getattr(original,'name',None)
        if name not in _TOOL_SPECS:
            harness.record('security','unknown_tool','block',ctx); continue
        schema,description=_TOOL_SPECS[name]
        def build(delegate,name,schema,description):
            async def invoke(**kwargs):
                try:
                    args=authorize_arguments(harness,name,kwargs,ctx)
                    data=await delegate.ainvoke(args)
                except GuardrailViolation:
                    return json.dumps({'ok':False,'error':'The harness denied this tool call.'})
                except Exception:
                    harness.record('structural','tool_backend_failure','block',ctx)
                    return json.dumps({'ok':False,'error':'The authorized MCP tool is temporarily unavailable.'})
                try:
                    if isinstance(data,str): data=json.loads(data)
                    if isinstance(data,list) and len(data)==1 and isinstance(data[0],dict) and data[0].get('type')=='text': data=json.loads(data[0]['text'])
                    data=ToolEnvelope.model_validate(data).model_dump(mode='json')
                except (ValidationError,ValueError,KeyError,TypeError):
                    harness.record('structural','tool_result_shape','block',ctx)
                    return json.dumps({'ok':False,'error':'The MCP result failed structural validation.'})
                if name in {'get_incident','update_incident_status','create_incident'}:
                    if data['ok'] and not isinstance(data['data'],dict):
                        harness.record('structural','tool_result_shape','block',ctx)
                        return json.dumps({'ok':False,'error':'The MCP result failed structural validation.'})
                    if isinstance(data['data'],dict):
                        allowed={'id','incident_id','order_id','tracking_number','title','description','status','category','origin','branch','priority','created_at','updated_at','resolved_at','country','owner_subject','customer_id','user_uuid','company'}
                        if set(data['data'])-allowed: harness.record('structural','tool_result_fields','redirect',ctx)
                        data['data']={k:v for k,v in data['data'].items() if k in allowed}
                isolated=harness.isolate_external(data,source='mcp:'+name,ctx=ctx)
                if on_result is not None and not isolated.get('blocked'): on_result(isolated.get('content',{}))
                return json.dumps(isolated,ensure_ascii=False)
            def invalid_arguments(error):
                harness.record('structural','tool_arguments','block',ctx)
                return 'The tool arguments failed harness validation.'
            return StructuredTool.from_function(coroutine=invoke,name=name,description=description,args_schema=schema,handle_validation_error=invalid_arguments)
        result.append(build(original,name,schema,description))
    return result
