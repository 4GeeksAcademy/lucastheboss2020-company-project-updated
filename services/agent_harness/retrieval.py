"""Use the existing retrieval/generation pipeline, isolating evidence before generation."""
from __future__ import annotations
import json
import re
import math
from data.process.rag import RetrievedChunk, retrieve
from data.pipelines.rag import OpenAICompatibleGenerationProvider, SYSTEM_PROMPT as GROUNDING_PROMPT, generate_answer
from services.knowledge_query import _GuardedGenerationProvider,UnsafeGeneratedAnswerError
from .models import GuardrailViolation
from .policy import SYSTEM_PROMPT, SAFE_FALLBACK


def isolate_chunks(chunks,harness,ctx):
    safe=[]
    for chunk in chunks:
        payload=getattr(chunk,'payload',None)
        if not isinstance(payload,dict) or not isinstance(payload.get('text'),str) or not payload.get('source_document') or not payload.get('section'):
            harness.record('structural','rag_chunk_shape','block',ctx); continue
        score=getattr(chunk,'score',None)
        if not all(isinstance(payload.get(key),str) and re.fullmatch(r'[A-Za-z0-9 _./()–—:-]{1,160}',payload[key]) for key in ['source_document','section']) or isinstance(score,bool) or not isinstance(score,(float,int)) or not math.isfinite(score):
            harness.record('structural','rag_metadata','block',ctx);continue
        country=payload.get('country')
        if country is not None and (not isinstance(country,str) or country not in {'US','ES','shared'}):
            harness.record('structural','rag_country_shape','block',ctx);continue
        if ctx.country and country not in {None,'shared',ctx.country}:
            harness.record('content','rag_country','redirect',ctx);continue
        if country is None and ctx.country:
            other=r'spain|españa' if ctx.country=='US' else r'united states|usa|los angeles|estados unidos'
            # Older chunks have no country field. Explicit regional policy headings
            # still must not enter another order country's context.
            text=' '.join(str(payload.get(key,'')) for key in ['source_document','section','text'])
            regional=rf'\b(?:{other})(?:[’\x27]s)?\s+(?:returns?|refunds?|policy|domestic sla)|\b(?:{other})\s*:\s*(?:returns?|refunds?|policy|\d)|(?:returns?|refunds?|policy)\s+(?:in|for)\s+(?:{other})\b'
            if re.search(regional,text,re.I):
                harness.record('content','rag_unlabeled_country','redirect',ctx);continue
        # Metadata is also external input; isolate it along with the document body.
        isolated=harness.isolate_external(payload,source='rag_document',ctx=ctx)
        if isolated.get('blocked'): continue
        clean=isolated['content']
        # Keep exact labels for citations while JSON-encoding control/tag delimiters.
        encoded=json.dumps({'source':'rag_document','trust':'untrusted_reference_data','facts':clean['text']},ensure_ascii=False).replace('<',chr(92)+'u003c').replace('>',chr(92)+'u003e')
        safe.append(RetrievedChunk(score=chunk.score,payload={**clean,'text':encoded}))
    return safe


def query_guarded(question,harness,ctx,*,retriever=None,provider=None):
    chunks=isolate_chunks((retriever or retrieve)(question),harness,ctx)
    if not chunks:
        return "I don't have enough safe, relevant TrackFlow evidence to answer that. Please confirm with the relevant TrackFlow team."
    base=provider or OpenAICompatibleGenerationProvider.from_env()
    class ShapeCheckedProvider:
        def generate(self,system,user):
            output=base.generate(system,user)
            if not isinstance(output,str) or not output.strip() or len(output)>12000:
                harness.record('structural','rag_answer_shape','block',ctx)
                raise GuardrailViolation('Invalid generated answer shape')
            return output
    guarded=_GuardedGenerationProvider(ShapeCheckedProvider(),question)
    class SecuredProvider:
        def generate(self,system_prompt,user_prompt):
            jurisdiction=f'Actual policy jurisdiction: {ctx.country}.' if ctx.country else 'No individual order country is established; do not guess.'
            return guarded.generate(SYSTEM_PROMPT+'\n'+GROUNDING_PROMPT+'\n'+jurisdiction,user_prompt)
    try:
        answer=generate_answer(question,chunks,SecuredProvider())
    except GuardrailViolation:
        return SAFE_FALLBACK
    except UnsafeGeneratedAnswerError:
        harness.record('content','rag_generation_validation','block',ctx);return SAFE_FALLBACK
    except Exception:
        harness.record('structural','rag_provider_unavailable','block',ctx);return SAFE_FALLBACK
    # Quantitative policy claims must be present in the allowed evidence, not a foreign chunk.
    evidence=' '.join(c.payload['text'] for c in chunks)+' '+' '.join(ctx.references)
    numbers=lambda text:{float(n) for n in re.findall(r'\d+(?:\.\d+)?',text)}
    claims=numbers(answer)
    if not claims.issubset(numbers(evidence)) or any(not math.isfinite(n) for n in claims):
        harness.record('content','rag_unsupported_fact','block',ctx);return SAFE_FALLBACK
    citations=re.findall(r'\[([^\[\]]{1,200})\]',answer)
    known={(c.payload['source_document'].strip(),c.payload['section'].strip()) for c in chunks}
    cited=[tuple(part.strip() for part in citation.split('|')) for citation in citations]
    insufficient=bool(re.search(r"don't have enough|do not have enough|cannot verify|couldn't verify",answer,re.I))
    if not insufficient and (not cited or any(citation not in known for citation in cited)):
        harness.record('content','rag_citation','block',ctx);return SAFE_FALLBACK
    return answer
