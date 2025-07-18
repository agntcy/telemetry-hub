# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

"""CLI entry point for the Metrics Computation Engine."""

import json
import sys
from pathlib import Path

import click
import requests
from dotenv import load_dotenv


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Metrics Computation Engine CLI.

    Use this CLI to interact with the Metrics Computation Engine.
    """
    # Load environment variables
    load_dotenv()


@cli.command()
def list_metrics():
    """List all available metrics."""
    try:
        # Import here to avoid circular imports during startup
        from metrics_computation_engine.registry import MetricRegistry

        registry = MetricRegistry()
        metrics = registry.list_metrics()

        if not metrics:
            click.echo("No metrics available.")
            return

        click.echo("Available metrics:")
        for metric in metrics:
            click.echo(f"  - {metric}")

    except Exception as e:
        click.echo(f"Error listing metrics: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("config_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--server-url",
    default="http://localhost:8000",
    help="URL of the MCE server",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for results (JSON format)",
)
def compute(config_file: Path, server_url: str, output: Path = None):
    """Compute metrics from a configuration file."""
    try:
        # Load configuration
        with open(config_file, "r") as f:
            config_data = json.load(f)

        click.echo(f"Loading configuration from: {config_file}")
        click.echo(f"Server URL: {server_url}")

        # Send request to server
        response = requests.post(
            f"{server_url}/compute_metrics",
            json=config_data,
            headers={"Content-Type": "application/json"},
            timeout=300,  # 5 minutes timeout
        )

        if response.status_code == 200:
            results = response.json()

            # Display results
            click.echo("\n✅ Metrics computation completed successfully!")
            click.echo(f"Computed {len(results.get('metrics', []))} metrics")

            # Save to output file if specified
            if output:
                with open(output, "w") as f:
                    json.dump(results, f, indent=2)
                click.echo(f"Results saved to: {output}")
            else:
                # Print summary to console
                click.echo("\nResults summary:")
                if "results" in results:
                    for session_id, session_results in results["results"].items():
                        click.echo(f"\nSession: {session_id}")
                        for (
                            metric_name,
                            metric_result,
                        ) in session_results.items():
                            click.echo(f"  {metric_name}: {metric_result}")
        else:
            click.echo(
                f"❌ Error: Server returned status {response.status_code}",
                err=True,
            )
            click.echo(f"Response: {response.text}", err=True)
            sys.exit(1)

    except FileNotFoundError:
        click.echo(f"❌ Configuration file not found: {config_file}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON in configuration file: {e}", err=True)
        sys.exit(1)
    except requests.ConnectionError:
        click.echo(
            f"❌ Cannot connect to server at {server_url}. "
            "Make sure the server is running.",
            err=True,
        )
        sys.exit(1)
    except requests.Timeout:
        click.echo(
            "❌ Request timed out. The computation may be taking too long.",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--server-url",
    default="http://localhost:8000",
    help="URL of the MCE server",
)
def health(server_url: str):
    """Check server health."""
    try:
        response = requests.get(f"{server_url}/health", timeout=10)
        if response.status_code == 200:
            click.echo("✅ Server is healthy")
        else:
            click.echo(f"❌ Server health check failed: {response.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        click.echo(f"❌ Cannot connect to server at {server_url}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Health check failed: {e}")
        sys.exit(1)


def main():
    """Main entry point for the mce-cli command."""
    cli()


if __name__ == "__main__":
    main()
