from google.adk.agents import LlmAgent

# --- Constants ---
GEMINI_MODEL = "gemini-2.5-flash"

# Create the recommender agent
task_input_agent = LlmAgent(
    name="task_input_agent",
    model=GEMINI_MODEL,
    instruction="""
    You are an assistant that waits, collects a phrase from the user, and then returns it as a list of strings.
    Once the user provides their phrase, replace all spaces with commas and create a list of strings
    No matter what the user's input phrase is
    Your *final and only* output should be the list of strings formatted as a comma-seperated array.
    For example, if the user enters **hi? how are you doing today**
    Your response should be **["hi?", "how", "are", "you", "doing", "today"]**
    Do not add any conversational fluff, greetings, or any other text to your final response.
    """,
    description="Returns all user input as a comma seperated list of strings.",
    output_key="task_list_input",
)
