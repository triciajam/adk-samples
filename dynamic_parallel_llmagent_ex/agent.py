from google.adk.agents import SequentialAgent

from .subagents.task_input_agent import task_input_agent
from .subagents.dynamic_parallel_llmagent import create_dynamic_parallel_llmagent

# Create the root sequential agent for the entire pipeline
root_agent = SequentialAgent(
    name="dynamic_parallel_llmagent_ex",
    sub_agents=[
        task_input_agent,
        create_dynamic_parallel_llmagent(),
    ],
    description=(
        "A toy agent that looks up the definiiton of every individual word in the user's input  "
        "in parallel (using dynamic_parallel_llmagent) and then returns all the definitions in a list."
    ),
)
