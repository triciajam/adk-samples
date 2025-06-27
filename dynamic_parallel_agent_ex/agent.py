from google.adk.agents import SequentialAgent

from .subagents.task_input_agent import task_input_agent
from .subagents.dynamic_parallel_agent import dynamic_parallel_agent

# Create the root sequential agent for the entire pipeline
root_agent = SequentialAgent(
    name="dynamic_parallel_agent_ex",
    sub_agents=[
        task_input_agent,
        dynamic_parallel_agent,
    ],
    description=(
        "A toy agent that counts the number of non-space characters in each word in a user's input "
        "in parallel (using dynamic_parallel_agent), and then totals up the character count for the entire input."
    ),
)
