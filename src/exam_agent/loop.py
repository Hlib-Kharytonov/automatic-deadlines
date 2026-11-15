from datetime import date

import anthropic
from dotenv import load_dotenv
from exam_agent.prompts import build_system_prompt
from exam_agent.tools import FINAL_TOOL, TOOL_DEFINITIONS, process_report, run_tool

load_dotenv()
client = anthropic.Anthropic()


class AgentError(Exception):
    """The agent stopped without a valid report_exams call."""


MAX_ROUNDS=10
def run_agent(task: str, mailbox, today: date | None = None) -> list[dict]:
    """Run the tool-use loop. Returns the exams from the first valid report_exams call."""
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
            # Claude ended its turn without reporting. That's a failure: the result
            # must come through report_exams, not as free text.
            texts=[block.text for block in response.content if block.type == "text"]
            raise AgentError(f"Claude stopped ({response.stop_reason}) without calling {FINAL_TOOL}:\n"
                             + "\n".join(texts))

        results=[]
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == FINAL_TOOL:
                print(f"  Claude asks: {FINAL_TOOL}({len(block.input['exams'])} exams)")
                try:
                    exams = process_report(block.input["exams"], mailbox)
                except ValueError as error:
                    # Send the problems back; Claude re-reads and calls report_exams again.
                    print(f"  Rejected:\n{error}")
                    results.append({"type":"tool_result","tool_use_id": block.id, "content":str(error),"is_error":True})
                    continue
                # Option A: a valid report ends the loop. No extra round for a summary.
                return exams

            print(f"  Claude asks: {block.name}({block.input})")
            try:
                content = run_tool(block.name,block.input,mailbox)
                results.append({"type":"tool_result","tool_use_id": block.id, "content":content})
            except ValueError as error:
                results.append({"type":"tool_result","tool_use_id": block.id, "content":str(error),"is_error":True})
        messages.append({"role":"user","content":results})
    raise AgentError(f"Stopped after {MAX_ROUNDS} rounds without a valid {FINAL_TOOL} call.")
