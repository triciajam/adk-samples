from google.adk.agents import LlmAgent

# --- Constants ---
GEMINI_MODEL = "gemini-2.5-flash"

# Create the recommender agent
task_input_agent = LlmAgent(
    name="task_input_agent",
    model=GEMINI_MODEL,
    instruction="""
    You are an assistant that collects a list of strings from the user.
    Politely ask the user to provide some thoughts.
    Once the user provides their response, replace all spaces with commas and create a list of strings
    Your *final and only* output should be the list of strings formatted as a comma-seperated array.
    For example, if the user enters **hi? how are you doing today**
    Your response should be **["hi", "how", "are", "you", "doing", "today"]**
    Do not add any conversational fluff, greetings, or any other text to your final response. You will save this result in the output key
    """,
    description="Asks the user for a comma seperated list of strings, and returns it as an array.",
    output_key="task_list_input",
)
