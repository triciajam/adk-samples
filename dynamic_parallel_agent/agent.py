from google.adk.agents import SequentialAgent

from .subagents.task_input_agent import task_input_agent
from .subagents.dynamic_parallel_task_agent import dynamic_parallel_task_agent

# Create the root sequential agent for the entire pipeline
root_agent = SequentialAgent(
    name="dynamic_parallel_agent",
    sub_agents=[
        task_input_agent,
        dynamic_parallel_task_agent,
    ],
    description=(
        "An agent that counts the number of non-space characters in a user's input by counting characters "
        "in each word in parallel (using dynamic_parallel_task_agent) and then totaling up the results for all words."
    ),
)
