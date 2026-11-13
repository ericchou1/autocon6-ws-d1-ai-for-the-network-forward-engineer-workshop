"""graph_agent.py — the same agent, built by hand as a LangGraph graph.

create_agent() is a convenience. Underneath it is this: a state (the message
list), a node that calls the model, a node that runs tools, and one
conditional edge that decides whether to loop or stop. Seeing it spelled out
is what lets you add your own nodes later — a second tool, an approval gate,
a memory checkpoint.
"""
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent import SYSTEM_PROMPT, ask, make_llm
from bgp_tool import get_bgp_state

tools = [get_bgp_state]
model = make_llm().bind_tools(tools)   # the model now knows the tool schema


# --- Node 1: call the model -------------------------------------------------
def call_model(state: MessagesState):
    """Prepend the system prompt, send the whole conversation, append the reply."""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    return {"messages": [model.invoke(messages)]}


# --- Node 2: run whatever tools the model asked for --------------------------
tool_node = ToolNode(tools)


# --- Wire it up --------------------------------------------------------------
graph = StateGraph(MessagesState)
graph.add_node("model", call_model)
graph.add_node("tools", tool_node)

graph.add_edge(START, "model")
# tools_condition inspects the model's last message: tool calls -> "tools",
# otherwise -> END. This single edge is the entire "agent loop".
graph.add_conditional_edges("model", tools_condition)
graph.add_edge("tools", "model")

agent = graph.compile()


if __name__ == "__main__":
    print("The graph, as Mermaid (paste into https://mermaid.live):\n")
    print(agent.get_graph().draw_mermaid())

    question = "Compare BGP state between r1 and r3."
    print(f"\n{'=' * 70}\nQuestion: {question}\n{'=' * 70}")
    print(f"\nFinal answer:\n{ask(agent, question)}")
