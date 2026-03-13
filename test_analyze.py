import asyncio
from agents.graph.workflow import build_workflow
from agents.state import IndiaEngineState
import datetime

async def main():
    state = {"ticker": "RELIANCE.NS", "horizon_days": 5, "analysis_date": str(datetime.date.today())}
    workflow = build_workflow()
    
    try:
        result = await workflow.ainvoke(state)
        print("Success:", result.keys())
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
