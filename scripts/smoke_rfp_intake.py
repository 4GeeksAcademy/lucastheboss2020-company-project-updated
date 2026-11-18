"""Optional real-provider smoke; public curriculum PDFs only. Never substitute fake agents."""

import argparse, asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.pipelines.rfp_intake.ingestion import convert_pdf
from data.pipelines.rfp_intake.graph import create_graph


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default="/tmp/trackflow-rfp-samples")
    parser.add_argument("--output", default="/tmp/m9-live-graph.json")
    args = parser.parse_args()
    results = []
    for i in (1, 2, 3):
        name = f"trackflow-request-{i}.pdf"
        print("Processing", name, flush=True)
        text = convert_pdf(Path(args.samples) / name)
        state = await create_graph(progress=lambda stage: print(stage, flush=True)).ainvoke(
            {"markdown": text, "sections": []}, {"recursion_limit": 10}
        )
        expected = ({"warehouse", "reverse"} if i == 1 else {"warehouse", "lastmile"}) if i != 3 else set()
        departments = {s["department_id"] for s in state.get("result", {}).get("sections", [])}
        accepted = state["classification"]["accepted"]
        currency = state.get("result", {}).get("metadata", {}).get("currency")
        passed = (
            accepted == (i != 3) and departments == expected and (i == 3 or currency == ("EUR" if i == 1 else "USD"))
        )
        results.append(
            {
                "sample": name,
                "passed": passed,
                "classification": state["classification"],
                "result": state.get("result"),
                "readability_metrics": state["metrics"],
            }
        )
        Path(args.output).write_text(
            json.dumps(
                {
                    "kind": "live configured-provider graph; public samples; not UI evidence",
                    "all_passed": all(r["passed"] for r in results),
                    "cases": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(name, "PASS" if passed else "FAIL", flush=True)
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
