# Dynamic Parallel Agent Example

This example demonstrates an advanced agent pattern for processing a dynamic list of tasks in parallel using a fixed-size pool of worker agents. The root agent orchestrates a pipeline that first asks the user for text input, splits that input into a list of words, and then uses the dynamic parallel pattern to count the characters of each word concurrently.

## Core Functionality

The primary agent in this example is the `dynamic_parallel_task_agent`. It is designed to solve a common problem: how to process a list of tasks where the number of tasks is unknown beforehand and may be larger than the number of parallel workers you can or want to run.

The agent pipeline is as follows:
1.  **Task Input**: An `LlmAgent` (`task_input_agent`) prompts the user for input and processes it into a list of strings (words).  This agent is just one example way to get a list of tasks into the session state.
2.  **Task Planning**: A `TaskPlannerAgent` takes this list and initializes a task queue in the session state.
3.  **Batch Processing Loop**: A `LoopAgent` (`task_batch_manager`) repeatedly executes a batch processing cycle until the task queue is empty.
    - **Termination Check**: A `TerminationChecker` agent checks if the queue is empty and stops the loop if it is.
    - **Task Distribution**: A `TaskDistributorAgent` takes a "batch" of tasks from the queue (up to the maximum number of workers) and assigns them to the worker agents.
    - **Parallel Execution**: A `ParallelAgent` (`worker_pool`) runs a fixed number of `WorkerAgent`s concurrently. Each worker picks up its assigned task, processes it (in this case, counts the characters), and writes the result back to the session state.
4.  **Result Aggregation**: Once the loop terminates, a `TaskAggregatorAgent` collects all the individual results and computes a final summary (the total character count).

## Why is this pattern needed?

The base Agent Development Kit (ADK) provides powerful components for building agentic workflows, including the `ParallelAgent` for concurrent execution. However, the `ParallelAgent` is designed to run a *predefined, static list* of sub-agents. It does not natively support scenarios where you have a *dynamic list* of work items that you want to distribute among a smaller, fixed-size pool of workers.

This `dynamic_parallel_agent` pattern addresses that gap by providing a reusable architecture for **dynamic task distribution and batch processing**.

### Limitations of Base ADK Components Addressed:

1.  **Static vs. Dynamic Parallelism**:
    - **`ParallelAgent` (Base ADK)**: Requires you to define the exact agents to be run in parallel at design time. It's perfect for when you have a fixed number of known, concurrent operations.
    - **This Pattern**: Handles a dynamic list of tasks (e.g., processing N files in a folder, where N is unknown). It creates a fixed pool of M workers and uses a loop to process all N tasks in batches of M, making it highly scalable and efficient.

2.  **Resource Management**:
    - **`ParallelAgent` (Base ADK)**: If you tried to create a new agent for every single task in a large list, you could quickly overwhelm system resources (e.g., memory, API rate limits).
    - **This Pattern**: Manages resources effectively by using a fixed-size worker pool. You can control the maximum degree of parallelism (`MAX_WORKERS`) to match the capacity of your system, preventing overload while still benefiting from concurrent processing.

3.  **Orchestration Logic**:
    - **Base ADK**: Provides the building blocks (`LoopAgent`, `ParallelAgent`, `SequentialAgent`).
    - **This Pattern**: Demonstrates how to combine these blocks with custom `BaseAgent`s for state management to create a sophisticated, stateful orchestration pipeline. It explicitly manages a task queue, distributes work, and aggregates results—logic that is not encapsulated in a single base ADK component but is crucial for many real-world applications.

In summary, this example provides a blueprint for building scalable, resource-aware agents that can handle large, dynamic workloads—a common requirement that extends beyond the basic capabilities of the standard ADK workflow agents.

## How to Run

### 1. Setup

First, create a virtual environment and install the required dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
pip install -r requirements.txt
```

### 2. Configure Environment Variables

This agent uses the Gemini API. You will need to set your Google API key as an environment variable. Create a `.env` file in the repo's root directory:

**.env**
```
GOOGLE_API_KEY="YOUR_API_KEY_HERE"
```

Replace `"YOUR_API_KEY_HERE"` with your actual Google API key.

### 3. Run the Agent

You can run the agent using the ADK CLI. From the repo's root directory, the following command will start a web-based development UI where you can interact with the agent:

```bash
adk web
```

Select `dynamic_parallel_agent_ex` in the top left of the web UI.

Type any text as input and the agent will calculate the total number of characters (not including spaces) in those words.

## Known Issues

The agent runs successfully and completes the tasks using `adk web`. However, there is one "Failed to detach context" opentelemmetry error in the logs for each worker.
These errors do not stop or interrupt agent execution or the web interface, but need to be resolved. Possibly related to this [open issue](https://github.com/open-telemetry/opentelemetry-python/issues/2606).

```
2025-06-19 20:16:43,953 - ERROR - __init__.py:157 - Failed to detach context
Traceback (most recent call last):
  File "C:\Users\trishjam.GOOGLE\Documents\trishjam\projects\25-adk-examples\.venv\Lib\site-packages\opentelemetry\context\__init__.py", line 155, in detach
    _RUNTIME_CONTEXT.detach(token)
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "C:\Users\trishjam.GOOGLE\Documents\trishjam\projects\25-adk-examples\.venv\Lib\site-packages\opentelemetry\context\contextvars_context.py", line 53, in detach
    self._current_context.reset(token)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
ValueError: <Token var=<ContextVar name='current_context' default={} at 0x0000025023412570> at 0x0000025030FEFC00> was created in a different Context
2025-06-19 20:16:43,954 - ERROR - __init__.py:157 - Failed to detach context
Traceback (most recent call last):
  File "C:\Users\trishjam.GOOGLE\Documents\trishjam\projects\25-adk-examples\.venv\Lib\site-packages\opentelemetry\context\__init__.py", line 155, in detach
    _RUNTIME_CONTEXT.detach(token)
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "C:\Users\trishjam.GOOGLE\Documents\trishjam\projects\25-adk-examples\.venv\Lib\site-packages\opentelemetry\context\contextvars_context.py", line 53, in detach
    self._current_context.reset(token)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
ValueError: <Token var=<ContextVar name='current_context' default={} at 0x0000025023412570> at 0x0000025030FEF580> was created in a different Context
...
```