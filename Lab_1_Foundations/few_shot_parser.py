"""few_shot_parser.py — same task as naive_parser.py, but with an example to imitate."""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# Model string lives on one line so it's easy to find and swap.
MODEL = "gpt-6-luna"

llm = ChatOpenAI(model=MODEL, reasoning_effort="none")

SYSTEM_PROMPT = """You are a network configuration parser. Given SR Linux BGP neighbor
output, extract each peer and return one JSON object per line, no commentary.

Example input:
| default       | 192.168.1.1          | example-grp   | S    | 65500  | established|

Example output:
{"peer_ip": "192.168.1.1", "group": "example-grp", "peer_as": 65500, "state": "established"}
"""

SAMPLE = """
| default       | 10.0.0.2             | ibgp-65001    | S    | 65001  | established|
| default       | 10.1.13.2            | ebgp-r3       | S    | 65002  | active     |
"""

response = llm.invoke([
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=SAMPLE),
])
print(response.content)
