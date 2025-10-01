# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import click
from pydantic import BaseModel, Field

from dotenv import load_dotenv
from metrics_computation_engine.dal.api_client import (
    get_api_client,
    get_all_session_ids,
    get_traces_by_session_ids,
    traces_processor,
)
from typing import Any, Optional
from datetime import datetime
from metrics_computation_engine.entities.models.session_set_printer import (
    print_statistics,
    display_session_set,
)
from metrics_computation_engine.models.requests import BatchConfig, BatchTimeRange
from metrics_computation_engine.logger import setup_logger

load_dotenv()

logger = setup_logger(__name__)


def datetime_valid(dt_str):
    try:
        datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class DalCliArgs(BaseModel):
    """
    Represent the arguments of the current script
    """

    limit: Optional[int] = Field(
        -1, description="Limit the number of tests to be retrieved by the analyzer"
    )
    start_time: Optional[str] = Field(
        None, description="Start time in ISO 8601 UTC format"
    )
    end_time: Optional[str] = Field(None, description="End time in ISO 8601 UTC format")
    prefix: Optional[str] = Field(None, description="Prefix for the evaluation")
    session_id: Optional[str] = Field(None, description="Single session ID to evaluate")
    file: Optional[str] = Field(
        None, description="Path to the file containing session data"
    )
    tree_depth: Optional[int] = Field(
        3, description="Maximum depth for tree display (default: 3)"
    )
    show_tree: Optional[bool] = Field(
        False, description="Display execution tree structure"
    )
    dump: Optional[bool] = Field(
        False, description="Dump the session data to a file (if not local mode)"
    )


def validate_limit(ctx, param, value):
    """Custom validation for limit parameter"""
    if value < -1 or value == 0:
        raise click.BadParameter(
            "limit argument must be a strict positive integer or -1 (no limit)"
        )
    return value


def validate_tree_depth(ctx, param, value):
    """Custom validation for tree_depth parameter"""
    if value < 1:
        raise click.BadParameter(
            "tree_depth argument must be a positive integer (minimum 1)"
        )
    return value


def validate_datetime(ctx, param, value):
    """Custom validation for datetime parameters"""
    if value is not None and not datetime_valid(value):
        raise click.BadParameter(
            f"{param.name} is not a valid ISO 8601 UTC datetime string"
        )
    return value


def create_batch_config(session_id=None, start_time=None, end_time=None, prefix=None):
    """
    Create a BatchConfig object from CLI arguments to match main.py approach.
    """
    batch_config = BatchConfig()

    # Set time range if provided
    if start_time and end_time:
        batch_config.time_range = BatchTimeRange(start=start_time, end=end_time)

    # Set app name/prefix if provided
    if prefix:
        batch_config.app_name = prefix

    # For single session ID case, we'll handle it differently in the caller
    # since main.py has separate paths for batch vs single session

    return batch_config


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--start_time", callback=validate_datetime, help="Start time in ISO 8601 UTC format"
)
@click.option(
    "--end_time", callback=validate_datetime, help="End time in ISO 8601 UTC format"
)
@click.option("--prefix", help="Prefix for the evaluation")
@click.option("--session_id", help="Single session ID to evaluate")
@click.option("--file", help="Path to the file containing session data")
@click.option(
    "--limit",
    default=-1,
    type=int,
    callback=validate_limit,
    help="Max number of populations to retrieve, -1 for no limit",
)
@click.option(
    "--show_tree", is_flag=True, default=False, help="Display execution tree structure"
)
@click.option(
    "--tree_depth",
    default=3,
    type=int,
    callback=validate_tree_depth,
    help="Maximum depth for tree display (default: 3)",
)
@click.option(
    "--dump",
    is_flag=True,
    default=False,
    help="Dump the session data to a file (if not local mode)",
)
def cli_command(**kwargs):
    """Poirot evaluator command line interface"""
    # No need to convert argument names since we're using underscores to match the original
    args_dict = kwargs.copy()

    # Validate interdependent arguments
    _validate_interdependent_args(args_dict)

    return DalCliArgs(**args_dict)


def _validate_interdependent_args(args_dict):
    """Validate arguments that depend on each other"""
    # Validate skip_existing_metrics dependency
    """if args_dict['skip_existing_metrics'] and not args_dict['metrics_writer']:
        raise click.BadParameter(
            "skip_existing_metrics can only be used with metrics_writer"
        )"""

    # Validate mutually exclusive argument groups
    file = args_dict["file"]
    start_time = args_dict["start_time"]
    end_time = args_dict["end_time"]
    prefix = args_dict["prefix"]
    session_id = args_dict["session_id"]

    # Count how many input sources are specified
    input_sources = []

    if session_id:
        input_sources.append("session_id")
    if file:
        input_sources.append("file")
    if start_time and end_time:
        input_sources.append("start_time+end_time")

    # Check for valid combinations
    if len(input_sources) == 0:
        raise click.BadParameter(
            "One of the following is required: --session_id, --file, or (--start_time and --end_time)"
        )

    if len(input_sources) > 1:
        raise click.BadParameter(
            f"Only one input source allowed, but got: {', '.join(input_sources)}"
        )

    # Special validation: start_time requires end_time and vice versa
    if (start_time and not end_time) or (end_time and not start_time):
        raise click.BadParameter(
            "Both --start_time and --end_time are required when using time range"
        )

    # Special validation: prefix can only be used with start_time+end_time
    if prefix and not (start_time and end_time):
        raise click.BadParameter(
            "--prefix can only be used with --start_time and --end_time"
        )


def set_main_args() -> DalCliArgs:
    """Parse command line arguments and return MainArgs instance"""
    import sys

    # Check if help is requested and handle it directly
    if "-h" in sys.argv or "--help" in sys.argv:
        cli_command.main(["--help"], standalone_mode=True)
        # This line should never be reached due to SystemExit from help
        return None

    try:
        # Use click's standalone_mode=False to get the result instead of printing/exiting
        result = cli_command.main(standalone_mode=False)
        # Make sure we got a DalCliArgs object, not an exit code
        if isinstance(result, DalCliArgs):
            return result
        else:
            # This shouldn't happen normally, but just in case
            raise SystemExit(f"Unexpected result type: {type(result)}")
    except click.ClickException as e:
        # Convert click exceptions to the format expected by the existing code
        raise SystemExit(f"Error: {e.message}")
    except SystemExit as e:
        # Re-raise SystemExit for help and other cases
        raise e


def run() -> None | Any:
    """
    Run the evaluator.

    Returns:
        EvaluatorResponse
    """
    args = set_main_args()

    logger.info(f"{args=}")

    # data retriever
    api_client = get_api_client(
        devlimit=args.limit,
        logger=logger,
    )

    # Load trace data based on input source
    not_found_sessions = []
    session_set = None

    if args.file:
        # Process traces directly from file using ApiClient
        session_set = api_client.load_session_set_from_file(args.file)
    elif args.session_id:
        # For specific session ID, use single session approach like main.py
        session_ids = [args.session_id]
        grouped_sessions, not_found_sessions = get_traces_by_session_ids(session_ids)
        # Then process the session set using traces_processor
        if grouped_sessions:
            session_set = traces_processor(grouped_sessions)
        else:
            # Create empty session set if no sessions found
            from metrics_computation_engine.entities.models.session_set import (
                SessionSet,
            )

            session_set = SessionSet(sessions=[], stats=None)
    elif args.start_time:
        # For time-based queries, use batch config approach like main.py
        batch_config = create_batch_config(
            start_time=args.start_time, end_time=args.end_time, prefix=args.prefix
        )
        # Validate the batch config
        if not batch_config.validate():
            logger.error("Invalid batch configuration")
            return None

        session_ids = get_all_session_ids(batch_config=batch_config)
        grouped_sessions, not_found_sessions = get_traces_by_session_ids(session_ids)
        # Then process the session set using traces_processor
        if grouped_sessions:
            session_set = traces_processor(grouped_sessions)
        else:
            # Create empty session set if no sessions found
            from metrics_computation_engine.entities.models.session_set import (
                SessionSet,
            )

            session_set = SessionSet(sessions=[], stats=None)
    else:
        logger.error(
            "No valid input source specified (file, session_id, or start_time)"
        )
        return None

    # Issue warning if there are not found sessions
    if not_found_sessions:
        logger.warning(
            f"⚠️  {len(not_found_sessions)} session(s) were not found in the API: {not_found_sessions}"
        )
        if args.session_id and args.session_id in not_found_sessions:
            logger.warning(
                f"⚠️  The specifically requested session '{args.session_id}' was not found!"
            )
    elif not args.file:  # Only show success message for API calls
        logger.info("✅ All requested sessions were found successfully")

    if args.show_tree:
        # Display results with execution trees
        display_session_set(
            session_set,
            show_summary=True,
            show_trees=args.show_tree,
            show_statistics=False,
            tree_depth=args.tree_depth,
        )

    try:
        print_statistics(session_set)
    except Exception as e:
        logger.error(f"Error while printing stats: {e}")
        logger.error(
            f"Failed to print statistics for {len(session_set.sessions)} sessions"
        )
        # Don't print the raw session_set object as it's too verbose

    return session_set


def main() -> None:
    """Main entry point for the CLI command."""
    try:
        run()
    except Exception as e:
        print(e)
        import traceback
        import sys

        traceback.print_exception(e, file=sys.stdout)


if __name__ == "__main__":
    main()
