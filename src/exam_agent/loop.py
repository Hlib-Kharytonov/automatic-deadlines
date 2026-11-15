from datetime import date

import anthropic
from dotenv import load_dotenv
from exam_agent.prompts import build_system_prompt
from exam_agent.tools import TOOL_DEFINITIONS, run_tool

load_dotenv()
client = anthropic.Anthropic()

MAX_ROUNDS=10
def run_agent(task: str, mailbox, today: date | None = None) -> str:
    system = build_system_prompt(today or date.today())
    messages=[{"role": "user", "content": task}]

    for round_number in range(1, MAX_ROUNDS + 1):
        response=client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=16000,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages
            )
        print(f"\n--- Round {round_number}: stop_reason={response.stop_reason}, "
              f"tokens in/out={response.usage.input_tokens}/{response.usage.output_tokens}")
        messages.append({"role":"assistant","content":response.content})

        if response.stop_reason != "tool_use":
            texts=[block.text for block in response.content if block.type == "text"]
            return "\n".join(texts)
        
        results=[]
        for block in response.content:
            if block.type == "tool_use":
                print(f"  Claude asks: {block.name}({block.input})")
                try:
                    content = run_tool(block.name,block.input,mailbox)
                    results.append({"type":"tool_result","tool_use_id": block.id, "content":content})
                except ValueError as error:
                    results.append({"type":"tool_result","tool_use_id": block.id, "content":str(error),"is_error":True})
        messages.append({"role":"user","content":results})
    return f"Stopped after {MAX_ROUNDS} rounds without finishing."
