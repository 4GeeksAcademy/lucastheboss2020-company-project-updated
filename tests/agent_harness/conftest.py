from pathlib import Path
import time
import pytest
from services.agent_harness.models import AuthenticatedSession,ResourceGrant
from services.agent_harness.observability import GuardrailEvents
from services.agent_harness.policy import AgentHarness

OWN='11111111-1111-4111-8111-111111111111'
OTHER='22222222-2222-4222-8222-222222222222'

@pytest.fixture
def us_session():
    return AuthenticatedSession(company='trackflow',subject='synthetic-owner',customer_type='B2C',country='US',expires_at=time.time()+3600,
        resources=(ResourceGrant(reference='US-1001',aliases=(OWN,'TRACKUS123'),owner_subject='synthetic-owner',company='trackflow',country='US'),
                   ResourceGrant(reference='45821',aliases=(OTHER,),owner_subject='another-customer',company='trackflow',country='ES')),
        active_reference='US-1001',permissions=('incidents:read',))

@pytest.fixture
def staff_session(us_session):
    return us_session.model_copy(update={'customer_type':'staff','permissions':('incidents:read','incidents:create','incidents:write','inventory:read')})

@pytest.fixture
def harness(tmp_path,us_session):
    return AgentHarness(us_session,events=GuardrailEvents(tmp_path/'guardrails.sqlite'),test_session='deterministic')
