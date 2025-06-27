"""
This module defines a reusable, dynamic, parallel task processing agent.

This agent is designed to take a list of tasks from a specified session key,
distribute them among a fixed-size pool of worker agents, process them in
parallel, and then aggregate the results. It is built to handle a number of
tasks that can be greater than the number of available workers by processing
the tasks in batches.

The main components are:
- TaskPlannerAgent: Initializes the process, creating a task queue.
- TaskDistributorAgent: Deals out a batch of tasks to workers in each loop.
- WorkerAgent: Performs the actual work on a single task.
- TerminationChecker: Determines when all tasks are processed and stops the loop.
- TaskAggregatorAgent: Collects and summarizes the results from all workers.

These components are orchestrated by a LoopAgent that manages the batch
processing and a top-level SequentialAgent that defines the overall pipeline.
"""

import json
import secrets
from typing import Optional
from google.adk.agents import (
    BaseAgent,
    LlmAgent,
    SequentialAgent,
    ParallelAgent,
    LoopAgent,
)
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.adk.events import Event, EventActions
from google.genai import types

# --- Configuration Constants ---

# The maximum number of worker agents to run in parallel.
MAX_WORKERS = 6
# The session key where the initial list of tasks is expected to be found.
TASK_LIST_SESSION_KEY = "task_list_input"


class TaskPlannerAgent(BaseAgent):
    """
    Initializes a processing run.

    This agent reads an initial list of tasks from a specified session key,
    creates a unique run ID, and sets up the initial state for the processing
    pipeline, including the main task queue and a backup of the original tasks.
    """

    def __init__(self, *, name: str, task_list_session_key: str):
        """
        Initializes the TaskPlannerAgent.

        Args:
            name: The name of the agent.
            task_list_session_key: The key in the session state where the initial
                list of tasks is stored.
        """
        super().__init__(name=name)
        self._task_list_session_key = task_list_session_key

    async def _run_async_impl(self, ctx):
        """The main execution logic for the TaskPlannerAgent."""
        run_id = secrets.token_hex(2)
        task_list_str = ctx.session.state.get(self._task_list_session_key, "[]")

        try:
            task_list = json.loads(task_list_str)
        except json.JSONDecodeError:
            task_list = []

        if not task_list:
            yield Event(
                author=self.name,
                content=types.Content(
                    role=self.name,
                    parts=[types.Part(text="No tasks found to process.")],
                ),
                actions=EventActions(escalate=True),
            )
            return

        # Set up the state for this run.
        task_queue_key = f"task_queue:{run_id}"
        original_tasks_key = f"original_tasks:{run_id}"
        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[
                    types.Part(
                        text=f"Run {run_id} planning to process {len(task_list)} tasks."
                    )
                ],
            ),
            actions=EventActions(
                state_delta={
                    "current_run": run_id,
                    task_queue_key: task_list,
                    original_tasks_key: list(task_list),
                }
            ),
        )


class TaskDistributorAgent(BaseAgent):
    """
    Distributes a batch of tasks from the main queue to the worker agents.

    In each iteration of the processing loop, this agent takes a number of tasks
    (up to `max_workers`) from the main task queue and assigns each one to a
    specific worker by creating a unique task key in the session state.
    """

    def __init__(self, *, name: str, max_workers: int):
        """
        Initializes the TaskDistributorAgent.

        Args:
            name: The name of the agent.
            max_workers: The maximum number of tasks to distribute in one batch.
        """
        super().__init__(name=name)
        self._max_workers = max_workers

    async def _run_async_impl(self, ctx):
        """The main execution logic for the TaskDistributorAgent."""
        run_id = ctx.session.state.get("current_run")
        if not run_id:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="No active run.")]),
            )
            return

        task_queue_key = f"task_queue:{run_id}"
        task_queue = ctx.session.state.get(task_queue_key, [])

        if not task_queue:
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="No tasks to distribute.")]
                ),
            )
            return

        # Distribute a batch of tasks, one for each available worker.
        batch_size = min(len(task_queue), self._max_workers)
        task_delta = {}
        for i in range(batch_size):
            worker_name = f"worker_{i}"
            next_task = task_queue.pop(0)
            # Create a unique key for this specific task assignment.
            task_key = f"task:{run_id}:{worker_name}:{secrets.token_hex(2)}"
            task_delta[task_key] = next_task

        # Update the main task queue in the session state.
        task_delta[task_queue_key] = task_queue

        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[types.Part(text=f"Distributing {batch_size} tasks.")],
            ),
            actions=EventActions(state_delta=task_delta),
        )


class WorkerLlmAgent(LlmAgent):
    """
    An LlmAgent worker that processes tasks assigned to it for a given run.

    Each worker looks for tasks in the session state that match its name and
    the current run ID. It processes each task it finds by invoking its own
    LLM and writes the result back to the session, using a key that correlates
    with the original task key.
    """

    async def _run_async_impl(self, ctx):
        """The main execution logic for the WorkerAgent."""
        run_id = ctx.session.state.get("current_run")
        if not run_id:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="No active run.")]),
            )
            return

        # Find all valid (non-None) tasks assigned to this specific worker.
        tasks_for_worker = {
            k: v
            for k, v in ctx.session.state.items()
            if k.startswith(f"task:{run_id}:{self.name}:") and v is not None
        }

        if not tasks_for_worker:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="No tasks for me.")]),
            )
            return

        task_delta = {}
        for task_key, task_data in tasks_for_worker.items():
            # The key this agent will write to.
            output_key = ":".join(["task_out"] + task_key.split(":")[1:])
            self.output_key = output_key

            print(
                f"In WorkerLlmAgent _run_async_impl {self.name} {task_data} {self.output_key}"
            )

            # The content for the LLM is the task data itself.
            ctx.user_content = task_data

            try:
                # Programmatically invoke the processing agent.
                async for event in super()._run_async_impl(ctx):
                    yield event
            except Exception as e:
                # If any error occurs, log it and record an error state.
                print(f"Worker {self.name} failed on task {task_data}: {e}")
                task_delta[output_key] = {
                    "error": f"Processing failed: {e}",
                    "worker": self.name,
                    "task_key": task_key,
                    "task_data": task_data,
                }
            finally:
                # ALWAYS mark the task as processed, whether it succeeded or failed.
                task_delta[task_key] = None

        yield Event(
            author=self.name,
            actions=EventActions(state_delta=task_delta),
        )


class TerminationChecker(BaseAgent):
    """
    Checks if the main task queue is empty and terminates the loop if so.

    This agent runs at the beginning of each loop iteration. If it finds that
    the task queue is empty, it escalates, which signals the parent LoopAgent
    to stop executing.
    """

    async def _run_async_impl(self, ctx):
        """The main execution logic for the TerminationChecker."""
        run_id = ctx.session.state.get("current_run")
        if not run_id:
            yield Event(actions=EventActions(escalate=True))
            return

        task_queue_key = f"task_queue:{run_id}"
        task_queue = ctx.session.state.get(task_queue_key, [])
        if not task_queue:
            # The queue is empty, so we escalate to terminate the loop.
            yield Event(
                author=self.name,
                content=types.Content(
                    role=self.name,
                    parts=[types.Part(text="Task queue empty. Terminating loop.")],
                ),
                actions=EventActions(escalate=True),
            )


class TaskAggregatorAgent(BaseAgent):
    """
    Aggregates the final results from all workers for a given run.

    After the processing loop has completed, this agent collects all the
    individual results from the session state and produces a final summary.
    """

    async def _run_async_impl(self, ctx):
        """The main execution logic for the TaskAggregatorAgent."""
        run_id = ctx.session.state.get("current_run")
        if not run_id:
            yield Event(
                author=self.name,
                content=types.Content(
                    role=self.name, parts=[types.Part(text="No run to aggregate.")]
                ),
                actions=EventActions(escalate=True),
            )
            return

        # Collect all valid (non-None) results for the current run.

        task_outputs = [
            v
            for k, v in ctx.session.state.items()
            if k.startswith(f"task_out:{run_id}") and v is not None
        ]

        yield Event(
            author=self.name,
            content=types.Content(
                role=self.name,
                parts=[types.Part(text=f"The outputs are {task_outputs}")],
            ),
            actions=EventActions(escalate=True),
        )


# --- Agent Composition ---


class TaskLoadingError(Exception):
    """Custom exception for when task information fails to load."""

    pass


async def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """Add the specific task to the LLM request."""
    task_input = callback_context.user_content

    if not task_input:
        raise TaskLoadingError("No task information provided in user content.")

    llm_request.append_instructions([f"The input phrase is **{task_input}**. "])

    # file_artifact = await callback_context.load_artifact(filename=artifact_id)
    # if file_artifact:
    #     file_content = types.Content(
    #         role="user",
    #         parts=[types.Part(text=f"This is **{artifact_id}**."), file_artifact],
    #     )
    #     llm_request.contents.append(file_content)
    # else:
    #     raise TaskLoadingError(f"Could not load artifact: {artifact_id}")

    return None


def create_dynamic_parallel_llmagent() -> SequentialAgent:
    """
    Creates a dynamic parallel processing agent with a configurable worker.

    Returns:
        A SequentialAgent that defines the entire processing pipeline.
    """
    # 1. Create a fixed-size pool of worker agents.
    workers = [
        WorkerLlmAgent(
            name=f"worker_{i}",
            model="gemini-2.5-flash",
            instruction=(
                "Return a one sentence definition of the input phrase in the form "
                "**input phrase**: **definition**.  Do NOT add any extra text or commentary."
            ),
            before_model_callback=before_model_callback,
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )
        for i in range(MAX_WORKERS)
    ]

    # 2. Create a ParallelAgent to run all workers concurrently.
    worker_pool = ParallelAgent(name="worker_pool", sub_agents=workers)

    # 3. Create a LoopAgent to manage the batch processing. In each loop, it:
    #    a. Checks if the main task queue is empty.
    #    b. Distributes the next batch of tasks.
    #    c. Runs the worker pool to process the batch.
    task_batch_manager = LoopAgent(
        name="task_batch_manager",
        sub_agents=[
            TerminationChecker(name="termination_checker"),
            TaskDistributorAgent(name="task_distributor", max_workers=MAX_WORKERS),
            worker_pool,
        ],
    )

    # 4. Create the final SequentialAgent that defines the entire pipeline.
    dynamic_parallel_llmagent = SequentialAgent(
        name="dynamic_parallel_llmagent",
        sub_agents=[
            # a. Plan the tasks from the initial session key.
            TaskPlannerAgent(
                name="task_planner", task_list_session_key=TASK_LIST_SESSION_KEY
            ),
            # b. Process all tasks in batches until the queue is empty.
            task_batch_manager,
            # c. Aggregate the final results.
            TaskAggregatorAgent(name="task_aggregator"),
        ],
        description=(
            """An agent that reads tasks from a session key, creates a set number of workers, """
            """dynamically assigns tasks to each worker until all tasks are complete, and then aggregates results from each task."""
        ),
    )

    return dynamic_parallel_llmagent
