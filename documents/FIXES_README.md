# XplainCrypto Nested Event Loop Fix

## Problem

We identified an issue in the logs where the Visualizer was failing with the following error:

```
ERROR - Error in Visualization agent: Cannot run the event loop while another loop is running
```

This occurs because the `visualizer_sync` function tries to create a new event loop when it's already running within an existing event loop context in the workflow manager. This is a common issue with async Python code when you try to nest event loops.

## Root Cause

1. The `workflow_manager.py` calls agent functions (including `visualizer_sync`) within a coroutine (async) context.
2. The `visualizer_sync` function was unconditionally creating a new event loop with `asyncio.new_event_loop()` regardless of whether it was already in an event loop.
3. The `workflow_manager.py` didn't properly handle Task objects returned by agent functions, only checking for coroutines.

## Solutions Implemented

1. In `visualizer_sync`:
   - Added detection for whether we're already in an event loop using `asyncio.get_event_loop()` and `loop.is_running()`
   - When already in an event loop, return an `asyncio.create_task()` instead of trying to create a new loop
   - When not in an event loop, create a new one as before

2. In `workflow_manager.py`:
   - Updated `wrapped_agent` to handle not just coroutines but also `asyncio.Task` objects returned by agent functions
   - Added proper logging and error handling for task/coroutine waiting

## Tests Added

We created several new test files to verify our fixes:

1. `tests/test_visualizer_nested_loop.py` - Tests specifically for the nested event loop fix in the Visualizer
2. `tests/test_visualizer_sync_fix.py` - Tests for the fixed `visualizer_sync` function to ensure it works in nested contexts
3. `tests/test_nested_event_loop.py` - An integrated test that simulates the actual workflow environment

## Test Results

All tests are now passing, confirming that the fixes work correctly. The visualizer is able to function properly within an existing event loop context, and the workflow manager can properly handle the tasks returned by the visualizer.

## How to Test

Run the tests to verify the fixes work properly:

```bash
python -m pytest tests/test_visualizer_nested_loop.py -v
python -m pytest tests/test_visualizer_sync_fix.py -v
python -m pytest tests/test_nested_event_loop.py -v
```

Additionally, you can run the full application to verify the fixes work in the real environment:

```bash
python -m uvicorn backend.main:app --reload
```

Then send a request to `/api/research` with a project like "ONDO" and verify the visualization step completes successfully without the "Cannot run the event loop while another loop is running" error.

## Implementation Details

### Changes to `visualizer_sync`

The updated function now checks whether it's already in an event loop before creating a new one:

```python
def visualizer_sync(state: Dict[str, Any], llm=None, logger: Optional[logging.Logger] = None, config=None) -> Dict[str, Any]:
    # ... (initialization code) ...
    
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_event_loop()
        is_running = loop.is_running()
    except RuntimeError:
        # No event loop exists in this thread
        is_running = False
    
    # Run visualizer in the appropriate way based on context
    if is_running:
        # We're already in an event loop - return a task instead of running a new loop
        logger.info("Detected running event loop, using create_task for async execution")
        
        if hasattr(state, 'to_dict'):
            state_dict = state.to_dict()
            return asyncio.create_task(visualizer.run_with_state_async(state, state_dict))
        else:
            return asyncio.create_task(visualizer.run_with_state_async(state, state))
    else:
        # Not in an event loop yet, create our own
        logger.info("No running event loop detected, creating new event loop")
        # ... (original code) ...
```

### Changes to `workflow_manager.py`

The updated `wrapped_agent` function now checks for Task objects as well as coroutines:

```python
# Check if result is a coroutine or asyncio Task
if inspect.iscoroutine(result) or asyncio.iscoroutine(result) or isinstance(result, asyncio.Task):
    logger.info(f"Agent function {step_name} returned a coroutine or task, awaiting it")
    updated_state = await result
```

## Potential Future Improvements

- Consider making all agent functions consistently use async patterns
- Implement more comprehensive error handling for async operations
- Add more tests for other potential event loop issues 