"""CLI entry point for hydra-heads - run AI CLI providers in parallel."""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

LOG_BASE_DIR = os.getenv("HYDRA_LOG_DIR", str(Path.home() / ".hydra" / "tasks"))


def _resolve_prompt(args: argparse.Namespace) -> str:
    """Resolve prompt from positional arg, --prompt-file, or stdin."""
    if args.prompt_file and args.prompt:
        raise SystemExit("ERROR: Cannot specify both positional prompt and --prompt-file")

    if args.prompt_file:
        if args.prompt_file == "-":
            prompt_text = sys.stdin.read().strip()
            if not prompt_text:
                raise SystemExit("ERROR: No prompt received from stdin")
            return prompt_text
        file_path = Path(args.prompt_file)
        if not file_path.is_file():
            raise SystemExit(f"ERROR: Prompt file does not exist: {args.prompt_file}")
        try:
            return file_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as read_error:
            raise SystemExit(f"ERROR: Cannot read prompt file: {read_error}")

    if args.prompt:
        if args.prompt == "-":
            prompt_text = sys.stdin.read().strip()
            if not prompt_text:
                raise SystemExit("ERROR: No prompt received from stdin")
            return prompt_text
        return args.prompt

    if not sys.stdin.isatty():
        prompt_text = sys.stdin.read().strip()
        if prompt_text:
            return prompt_text

    raise SystemExit("ERROR: No prompt provided. Use positional arg, --prompt-file, or pipe to stdin.")


def _run_status_check(args: argparse.Namespace) -> None:
    """Ping all providers and display health status table."""
    import json
    from hydra_heads.core import (
        HydraError, _preflight_ping, _resolve_command,
        PREFLIGHT_PING_TIMEOUT_SECONDS,
    )
    from hydra_heads.providers import get_provider, list_providers

    provider_names = list_providers()
    provider_configs = [get_provider(name) for name in provider_names]

    commands = {}
    binary_missing = []
    for provider_config in provider_configs:
        try:
            commands[provider_config["name"]] = _resolve_command(provider_config)
        except HydraError:
            binary_missing.append(provider_config["name"])

    reachable_configs = [pc for pc in provider_configs if pc["name"] not in binary_missing]
    ping_timeout = args.ping_timeout if hasattr(args, "ping_timeout") else PREFLIGHT_PING_TIMEOUT_SECONDS

    healthy_names = set()
    ping_failed_names = set()
    if reachable_configs:
        try:
            healthy_configs = _preflight_ping(
                reachable_configs, commands, ping_timeout,
            )
            healthy_names = {pc["name"] for pc in healthy_configs}
        except HydraError:
            pass
        ping_failed_names = {pc["name"] for pc in reachable_configs} - healthy_names

    print(f"\n{'Provider':<12} {'Binary':<16} {'Status':<12}")
    print(f"{'-'*12} {'-'*16} {'-'*12}")
    for name in provider_names:
        config = get_provider(name)
        binary = config["binary"]
        if name in binary_missing:
            status = "NOT FOUND"
        elif name in ping_failed_names:
            status = "UNHEALTHY"
        elif name in healthy_names:
            status = "HEALTHY"
        else:
            status = "UNKNOWN"
        print(f"{name:<12} {binary:<16} {status:<12}")
    print()


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser with sensible defaults."""
    from hydra_heads.providers import list_providers

    available = list_providers()
    parser = argparse.ArgumentParser(
        prog="hydra-heads",
        description="Run multiple AI CLI tools in parallel with a shared prompt",
    )
    parser.add_argument("prompt", nargs="?", default=None,
                        help="Prompt to send to all selected providers (use - for stdin)")
    parser.add_argument("--prompt-file", metavar="FILE",
                        help="Read prompt from a file (use - for stdin)")
    def _safe_int_env(var_name: str, fallback: int, minimum: int = None) -> int:
        raw_value = os.getenv(var_name)
        if raw_value is None:
            return fallback
        try:
            parsed_value = int(raw_value)
        except ValueError:
            logger_cli = logging.getLogger("hydra_heads")
            logger_cli.warning(f"Invalid integer for {var_name}={raw_value!r}, using default {fallback}")
            return fallback
        if minimum is not None and parsed_value < minimum:
            logger_cli = logging.getLogger("hydra_heads")
            logger_cli.warning(f"{var_name}={parsed_value} below minimum {minimum}, using default {fallback}")
            return fallback
        return parsed_value

    default_providers = os.getenv("HYDRA_PROVIDERS", ",".join(available))
    default_timeout = _safe_int_env("HYDRA_TIMEOUT", 1800, minimum=1)
    default_retries = _safe_int_env("HYDRA_RETRIES", 0, minimum=0)
    default_ping_timeout = _safe_int_env("HYDRA_PING_TIMEOUT", 20, minimum=1)
    default_cwd = os.getenv("HYDRA_CWD")

    parser.add_argument("--providers", default=default_providers,
                        metavar="NAME,NAME,...",
                        help=f"Comma-separated providers to run (env: HYDRA_PROVIDERS, default: all). Choices: {', '.join(available)}")
    parser.add_argument("--log-dir", default=LOG_BASE_DIR,
                        help=f"Base directory for task logs (env: HYDRA_LOG_DIR, default: {LOG_BASE_DIR})")
    parser.add_argument("--cwd", default=default_cwd, metavar="DIR",
                        help="Working directory for provider execution (env: HYDRA_CWD)")
    parser.add_argument("--timeout", type=int, default=default_timeout, metavar="SECONDS",
                        help=f"Max seconds per provider (env: HYDRA_TIMEOUT, default: {default_timeout})")
    parser.add_argument("--fail-fast", action="store_true",
                        default=os.getenv("HYDRA_FAIL_FAST", "").lower() in ("1", "true", "yes"),
                        help="Abort all remaining providers on first failure (env: HYDRA_FAIL_FAST)")
    parser.add_argument("--ignore-errors", action="store_true",
                        default=os.getenv("HYDRA_IGNORE_ERRORS", "").lower() in ("1", "true", "yes"),
                        help="Suppress failure warnings in output (env: HYDRA_IGNORE_ERRORS)")
    parser.add_argument("--retries", type=int, default=default_retries, metavar="N",
                        help=f"Retry failed providers N times (env: HYDRA_RETRIES, default: {default_retries})")
    parser.add_argument("--stream", action="store_true",
                        default=os.getenv("HYDRA_STREAM", "").lower() in ("1", "true", "yes"),
                        help="Show live TUI output from each provider (env: HYDRA_STREAM)")
    parser.add_argument("--no-preflight", action="store_true",
                        default=os.getenv("HYDRA_NO_PREFLIGHT", "").lower() in ("1", "true", "yes"),
                        help="Skip the preflight ping check (env: HYDRA_NO_PREFLIGHT)")
    parser.add_argument("--ping-timeout", type=int, default=default_ping_timeout, metavar="SECONDS",
                        help=f"Timeout for preflight ping (env: HYDRA_PING_TIMEOUT, default: {default_ping_timeout})")
    parser.add_argument("--model", action="append", metavar="PROVIDER:MODEL",
                        help="Override model for a provider (e.g. --model claude:sonnet --model codex:gpt-4o). Repeatable.")
    parser.add_argument("--schema", action="store_true",
                        help="Print the JSON output schema and exit")
    parser.add_argument("--status", action="store_true",
                        help="Check health of all providers (ping test) and exit")
    parser.add_argument("--quiet", "-q", action="store_true",
                        default=os.getenv("HYDRA_QUIET", "").lower() in ("1", "true", "yes"),
                        help="Suppress all log output to stderr (env: HYDRA_QUIET)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    return parser


def main() -> None:
    """Parse arguments, run hydra, print JSON result to stdout."""
    parser = build_parser()
    args = parser.parse_args()

    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout must be a positive integer")
    if args.ping_timeout is not None and args.ping_timeout <= 0:
        parser.error("--ping-timeout must be a positive integer")
    if args.retries < 0:
        parser.error("--retries must be >= 0")

    from hydra_heads.core import HydraError, run_hydra, setup_logging

    setup_logging(verbose=args.verbose, quiet=args.quiet)

    if args.schema:
        import json
        from hydra_heads.core import OUTPUT_SCHEMA
        print(json.dumps(OUTPUT_SCHEMA, indent=2))
        return

    if args.status:
        _run_status_check(args)
        return

    try:
        prompt = _resolve_prompt(args)
        provider_names_raw = [name for name in (p.strip() for p in args.providers.split(",")) if name]
        seen_providers = set()
        provider_names = []
        for name in provider_names_raw:
            if name not in seen_providers:
                seen_providers.add(name)
                provider_names.append(name)
        if not provider_names:
            raise SystemExit("ERROR: No providers specified")
        from hydra_heads.providers import list_providers as _list_providers
        available_providers = _list_providers()
        unknown_providers = [name for name in provider_names if name not in available_providers]
        if unknown_providers:
            raise SystemExit(
                f"ERROR: Unknown provider(s): {', '.join(unknown_providers)}. "
                f"Available: {', '.join(available_providers)}"
            )
        model_overrides = {}
        if args.model:
            for model_spec in args.model:
                if ":" not in model_spec:
                    raise SystemExit(f"ERROR: --model must be PROVIDER:MODEL format, got '{model_spec}'")
                provider_part, model_part = model_spec.split(":", 1)
                if provider_part not in available_providers:
                    raise SystemExit(f"ERROR: Unknown provider in --model: '{provider_part}'")
                model_overrides[provider_part] = model_part

        result_json = run_hydra(
            prompt=prompt,
            provider_names=provider_names,
            log_base_directory=args.log_dir,
            timeout_seconds=args.timeout,
            working_directory=args.cwd,
            fail_fast=args.fail_fast,
            ignore_errors=args.ignore_errors,
            retries=args.retries,
            stream=args.stream,
            preflight=not args.no_preflight,
            ping_timeout=args.ping_timeout,
            model_overrides=model_overrides if model_overrides else None,
        )
        print(result_json)
    except HydraError as hydra_error:
        raise SystemExit(f"ERROR: {hydra_error}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
