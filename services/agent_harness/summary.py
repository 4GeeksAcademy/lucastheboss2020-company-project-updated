"""Read only command: python -m services.agent_harness.summary --session demo."""
import argparse
import json
from .observability import GuardrailEvents

def main():
    parser=argparse.ArgumentParser(description='Summarize retained TrackFlow guardrail events for a test session.')
    parser.add_argument('--session',required=True)
    parser.add_argument('--db',default='services/agent_harness/runtime/guardrails.sqlite')
    args=parser.parse_args()
    print(json.dumps(GuardrailEvents(args.db).summary(args.session),indent=2))

if __name__=='__main__': main()
