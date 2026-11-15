"""The tools Claude can call: their definitions, and the code that runs them.

TOOL_DEFINITIONS is sent to Claude with every request. Claude reads the names,
descriptions and input schemas to decide what to call. Claude never runs anything:
it only asks, and run_tool() does the work.
"""

import json

TOOL_DEFINITIONS = [
    {
        "name": "search_emails",
        "description": (
            "Search the student's mailbox. Returns up to 20 matching emails, newest first, "
            "each with id, sender, date, subject and a short snippet (not the full text). "
            "Words separated by spaces must all appear; put OR between alternatives, "
            "e.g. 'partiel OR examen OR CC'. Matching ignores case and accents but "
            "matches whole words only: 'CC' does not match 'CC1'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search words, e.g. 'partiel OR examen'"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "read_email",
        "description": (
            "Return the full text of one email: id, sender, date, subject and body. "
            "Use an id from search_emails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "An id returned by search_emails"},
            },
            "required": ["email_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def run_tool(name: str, tool_input: dict, mailbox) -> str:
    """Run one tool and return its result as a JSON string for Claude.

    Raises ValueError for bad input (unknown tool, unknown email id). The loop
    should catch it and send the message back to Claude as an error result.
    """
    if name == "search_emails":
        result = mailbox.search(tool_input["query"])
    elif name == "read_email":
        result = mailbox.read(tool_input["email_id"])
    else:
        raise ValueError(f"Unknown tool {name!r}.")
    return json.dumps(result, ensure_ascii=False)
