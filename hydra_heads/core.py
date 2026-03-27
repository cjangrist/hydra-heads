"""Run multiple AI CLI providers in parallel, log all output to files unbuffered, return JSON."""

import hashlib
import json
import logging
import os
import re
import signal
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, wait as futures_wait
from datetime import datetime, timezone
from pathlib import Path

import coloredlogs
from dotenv import load_dotenv
from sh import Command, CommandNotFound, TimeoutException

from hydra_heads.providers import get_provider, list_providers

load_dotenv()

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
LOG_BASE_DIR = os.getenv("HYDRA_LOG_DIR", str(Path.home() / ".hydra" / "tasks"))
MAX_PROMPT_ARG_BYTES = 131072
PREFLIGHT_PING_PROMPT = "respond with just the word pong"
PREFLIGHT_PING_TIMEOUT_SECONDS = 20
SIGTERM_GRACE_PERIOD_SECONDS = 5
WAIT_POLL_INTERVAL_SECONDS = 0.5
STREAM_BUFFER_MAX_CHUNKS = 500
STREAM_PANEL_HEIGHT = 6

logger = logging.getLogger("hydra_heads")

OUTPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "hydra-heads output",
    "type": "object",
    "additionalProperties": {
        "type": "object",
        "required": ["response", "exit_code", "latency_seconds", "status", "logs"],
        "properties": {
            "response": {"type": "string", "description": "Full text output from the provider"},
            "exit_code": {"type": "integer", "description": "Process exit code (0=success, -1=timeout, -2=aborted, -3=collection_timeout, -4=error)"},
            "latency_seconds": {"type": "number", "description": "Wall-clock seconds from launch to completion"},
            "status": {"type": "string", "enum": ["success", "failed", "timeout", "aborted", "collection_timeout", "error"]},
            "logs": {
                "type": "object",
                "properties": {
                    "stdout": {"type": "string", "description": "Path to stdout log file"},
                    "stderr": {"type": "string", "description": "Path to stderr log file"},
                },
            },
            "attempts": {
                "type": "array",
                "description": "Per-attempt details when retries are enabled",
                "items": {
                    "type": "object",
                    "properties": {
                        "attempt": {"type": "integer"},
                        "exit_code": {"type": "integer"},
                        "status": {"type": "string"},
                        "latency_seconds": {"type": "number"},
                        "logs": {"type": "object"},
                    },
                },
            },
        },
    },
    "description": "Top-level keys are provider names. Each value contains the provider's result.",
}


class HydraError(Exception):
    """Raised for user-facing errors in hydra-heads core library."""
    pass


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure colorized console logging to stderr."""
    logger.debug(f"setup_logging called with verbose={verbose} quiet={quiet}")
    if quiet:
        logger.setLevel(logging.CRITICAL + 1)
        logger.handlers.clear()
        return
    level = logging.DEBUG if verbose else logging.INFO
    coloredlogs.install(
        level=level,
        logger=logger,
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    logger.debug("setup_logging complete")


def _resolve_command(provider_config: dict):
    """Resolve a sh Command from a provider config, raising clear errors if missing."""
    binary_name = provider_config["binary"]
    logger.debug(f"_resolve_command resolving binary={binary_name}")
    try:
        resolved = Command(binary_name)
        logger.debug(f"_resolve_command resolved {binary_name}")
        return resolved
    except CommandNotFound:
        raise HydraError(f"'{binary_name}' CLI not found on PATH")


def _detect_model(provider_config: dict, model_override: str = None) -> str:
    """Detect the model a provider will use. Returns model name or empty string."""
    name = provider_config["name"]

    model_flag = provider_config.get("model_flag")

    if model_override and model_flag:
        return model_override
    if model_flag:
        args = provider_config.get("args", [])
        if model_flag in args:
            flag_index = args.index(model_flag)
            if flag_index + 1 < len(args):
                return args[flag_index + 1]

    detect_command = provider_config.get("model_detect_command")
    if detect_command:
        try:
            import subprocess
            result = subprocess.run(
                detect_command, shell=True, capture_output=True, text=True, timeout=5,
            )
            detected = result.stdout.strip()
            if detected:
                return detected
        except Exception as detect_error:
            logger.debug(f"{name} model detection failed: {detect_error}")

    return ""


def _make_display_name(provider_name: str, model_name: str) -> str:
    """Build display name like 'claude--opus' from provider name and model. Filesystem-safe."""
    if model_name:
        safe_model = re.sub(r'[^\w\-.]', '_', model_name)
        return f"{provider_name}--{safe_model}"
    return provider_name


def _build_command_args(provider_config: dict, prompt: str, model_override: str = None) -> list:
    """Build the full argument list for a provider invocation, optionally overriding the model."""
    logger.debug(f"_build_command_args for provider={provider_config['name']}")
    command_args = list(provider_config["args"])

    model_flag = provider_config.get("model_flag")
    if model_override and not model_flag:
        logger.warning(f"{provider_config['name']} does not support --model override (no model_flag configured)")
    if model_override and model_flag:
        if model_flag in command_args:
            flag_index = command_args.index(model_flag)
            if flag_index + 1 < len(command_args):
                command_args[flag_index + 1] = model_override
            else:
                command_args.append(model_override)
        else:
            command_args.extend([model_flag, model_override])
        logger.info(f"{provider_config['name']} model override: {model_override}")

    if provider_config["prompt_flag"]:
        command_args.extend([provider_config["prompt_flag"], prompt])
    else:
        command_args.append(prompt)
    logger.debug(f"_build_command_args result={command_args[:3]}...")
    return command_args


def _build_environment(provider_config: dict) -> dict:
    """Build environment dict, merging provider-specific vars into current env."""
    logger.debug(f"_build_environment for provider={provider_config['name']}")
    extra_environment = provider_config.get("env", {})
    if not extra_environment:
        logger.debug("_build_environment no extra vars, returning None")
        return None
    merged_environment = os.environ.copy()
    merged_environment.update(extra_environment)
    logger.debug(f"_build_environment merged {len(extra_environment)} extra vars")
    return merged_environment


def _kill_process_group(pid: int, sig: int) -> bool:
    """Send signal to entire process group. Returns True if signal was sent, False if process gone."""
    try:
        os.killpg(pid, sig)
        return True
    except (ProcessLookupError, OSError):
        return False


def _force_kill(process, provider_name: str) -> None:
    """SIGTERM with grace period, escalating to SIGKILL. Kills entire process group."""
    if not _kill_process_group(process.pid, signal.SIGTERM):
        try:
            process.wait(timeout=1)
        except Exception:
            pass
        return
    try:
        process.wait(timeout=SIGTERM_GRACE_PERIOD_SECONDS)
        logger.debug(f"{provider_name} terminated gracefully after SIGTERM")
    except (TimeoutException, Exception):
        logger.warning(f"{provider_name} did not terminate gracefully, sending SIGKILL")
        try:
            _kill_process_group(process.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            process.wait(timeout=10)
        except Exception as reap_error:
            logger.warning(f"{provider_name} could not be reaped after SIGKILL: {reap_error}")


def _build_task_hash(prompt: str) -> str:
    """Generate a hash from the prompt for task directory naming."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _prepare_task_directory(log_base_directory: str, prompt: str) -> str:
    """Create and return a fully qualified task directory: base/iso_datetime-task_hash-uuid/."""
    logger.debug(f"_prepare_task_directory base={log_base_directory}")
    iso_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    task_hash = _build_task_hash(prompt)
    unique_suffix = uuid.uuid4().hex[:8]
    task_directory_name = f"{iso_timestamp}-{task_hash}-{unique_suffix}"
    task_path = Path(log_base_directory).resolve() / task_directory_name
    try:
        task_path.mkdir(parents=True, exist_ok=True)
    except OSError as mkdir_error:
        raise HydraError(f"Cannot create log directory {task_path}: {mkdir_error}")
    logger.debug(f"_prepare_task_directory created {task_path}")
    return str(task_path)


def _prepare_log_paths(task_directory: str, provider_names: list) -> dict:
    """Return fully qualified stdout/stderr log file paths for all providers in task directory."""
    logger.debug(f"_prepare_log_paths task_directory={task_directory} providers={provider_names}")
    paths = {
        f"{name}_{stream}": str(Path(task_directory) / f"{name}_{stream}.log")
        for name in provider_names
        for stream in ("stdout", "stderr")
    }
    logger.debug(f"_prepare_log_paths created {len(paths)} log paths")
    return paths


def _preflight_ping(provider_configs: list, commands: dict,
                    log_base_directory: str, ping_timeout: int = PREFLIGHT_PING_TIMEOUT_SECONDS,
                    abort_event: threading.Event = None,
                    running_processes: dict = None,
                    process_lock: threading.Lock = None) -> list:
    """Run a quick ping prompt against all providers to verify they're responsive. Returns list of healthy configs."""
    import shutil
    import tempfile

    logger.info(f"Preflight ping: testing {len(provider_configs)} providers (timeout={ping_timeout}s)")
    ping_directory = tempfile.mkdtemp(prefix="hydra_ping_")

    if abort_event is None:
        abort_event = threading.Event()
    if running_processes is None:
        running_processes = {}
    if process_lock is None:
        process_lock = threading.RLock()

    try:
        ping_log_paths = _prepare_log_paths(ping_directory, [pc["name"] for pc in provider_configs])

        def ping_provider(provider_config: dict) -> tuple:
            name = provider_config["name"]
            return _launch_and_collect(
                commands[name], provider_config, PREFLIGHT_PING_PROMPT,
                ping_log_paths[f"{name}_stdout"], ping_log_paths[f"{name}_stderr"],
                timeout_seconds=ping_timeout, abort_event=abort_event,
                running_processes=running_processes, process_lock=process_lock,
            )

        with ThreadPoolExecutor(max_workers=len(provider_configs)) as executor:
            futures = {
                executor.submit(ping_provider, pc): pc["name"]
                for pc in provider_configs
            }
            ping_results = {}
            for future in as_completed(futures):
                future_name = futures[future]
                try:
                    name, result_data = future.result()
                except Exception as ping_error:
                    logger.warning(f"Preflight {future_name} raised {type(ping_error).__name__}: {ping_error}")
                    name = future_name
                    result_data = {"status": "error", "latency_seconds": 0}
                ping_results[name] = result_data

        healthy_providers = []
        failed_providers = []
        for provider_config in provider_configs:
            name = provider_config["name"]
            result = ping_results.get(name, {})
            status = result.get("status", "unknown")
            latency = result.get("latency_seconds", 0)
            if status == "success":
                logger.info(f"Preflight OK: {name} ({latency}s)")
                healthy_providers.append(provider_config)
            else:
                logger.warning(f"Preflight FAILED: {name} ({status}, {latency}s) — excluding from run")
                failed_providers.append(name)

        if failed_providers:
            logger.warning(f"Preflight excluded {len(failed_providers)} provider(s): {', '.join(failed_providers)}")

        if not healthy_providers:
            raise HydraError("All providers failed preflight ping — nothing to run")

        return healthy_providers
    finally:
        shutil.rmtree(ping_directory, ignore_errors=True)


def _launch_and_collect(command, provider_config: dict, prompt: str,
                        stdout_log: str, stderr_log: str,
                        timeout_seconds: int = None, working_directory: str = None,
                        streaming_buffer: deque = None, abort_event: threading.Event = None,
                        running_processes: dict = None,
                        process_lock: threading.Lock = None,
                        model_override: str = None) -> tuple:
    """Launch a CLI command with timeout, cwd, streaming, and abort support. Returns (name, result_dict)."""
    if process_lock is None:
        process_lock = threading.RLock()
    provider_name = provider_config["name"]

    if abort_event and abort_event.is_set():
        logger.info(f"{provider_name} aborted before launch (--fail-fast)")
        return (provider_name, {
            "response": "",
            "exit_code": -2,
            "latency_seconds": 0,
            "status": "aborted",
            "logs": {"stdout": stdout_log, "stderr": stderr_log},
        })

    command_args = _build_command_args(provider_config, prompt, model_override=model_override)
    environment = _build_environment(provider_config)
    logger.info(f"Launching {provider_name}")

    sh_kwargs = {
        "_out": stdout_log,
        "_err": stderr_log,
        "_out_bufsize": 0,
        "_err_bufsize": 0,
        "_tty_out": False,
        "_bg": True,
        "_bg_exc": False,
        "_new_session": True,
    }

    stop_polling = None
    poll_thread = None

    if streaming_buffer is not None:
        stop_polling = threading.Event()

        def poll_log_file():
            stdout_position = 0
            stderr_position = 0
            while not stop_polling.is_set():
                try:
                    current_size = os.path.getsize(stdout_log)
                    if current_size < stdout_position:
                        stdout_position = 0
                    if current_size > stdout_position:
                        with open(stdout_log, "rb") as log_file:
                            log_file.seek(stdout_position)
                            new_bytes = log_file.read()
                            if new_bytes:
                                chunk = new_bytes.decode("utf-8", errors="replace")
                                streaming_buffer.append(chunk)
                                stdout_position += len(new_bytes)
                except (FileNotFoundError, OSError):
                    pass
                except Exception:
                    break
                try:
                    stderr_size = os.path.getsize(stderr_log)
                    if stderr_size < stderr_position:
                        stderr_position = 0
                    if stderr_size > stderr_position:
                        with open(stderr_log, "rb") as log_file:
                            log_file.seek(stderr_position)
                            new_bytes = log_file.read()
                            if new_bytes:
                                chunk = new_bytes.decode("utf-8", errors="replace")
                                streaming_buffer.append(chunk)
                                stderr_position += len(new_bytes)
                except (FileNotFoundError, OSError):
                    pass
                except Exception:
                    break
                stop_polling.wait(0.15)

        poll_thread = threading.Thread(target=poll_log_file, daemon=True)
        poll_thread.start()

    if environment:
        sh_kwargs["_env"] = environment

    if working_directory:
        sh_kwargs["_cwd"] = working_directory

    # DESIGN: There is a small window between command() returning and the process being
    # registered in running_processes. If SIGINT fires in this window, this process is not
    # killed by the signal handler. This is acceptable: the process is registered immediately
    # after launch (before any logging), and the post-launch abort_event check below catches
    # the case where abort was signaled during this window and force-kills the process.
    start_time = time.monotonic()
    try:
        process = command(*command_args, **sh_kwargs)
    except Exception:
        if stop_polling:
            stop_polling.set()
        if poll_thread:
            poll_thread.join(timeout=5)
        raise

    if running_processes is not None:
        with process_lock:
            running_processes[provider_name] = process
    logger.info(f"{provider_name} started (pid={process.pid})")

    if abort_event and abort_event.is_set():
        logger.info(f"{provider_name} launched but abort already set, terminating")
        _force_kill(process, provider_name)
        if running_processes is not None:
            with process_lock:
                running_processes.pop(provider_name, None)
        if stop_polling:
            stop_polling.set()
        if poll_thread:
            poll_thread.join(timeout=5)
            if poll_thread.is_alive():
                logger.warning(f"{provider_name} poll thread did not stop cleanly")
        return (provider_name, {
            "response": "",
            "exit_code": -2,
            "latency_seconds": round(time.monotonic() - start_time, 2),
            "status": "aborted",
            "logs": {"stdout": stdout_log, "stderr": stderr_log},
        })

    timed_out = False
    aborted_during_wait = False
    deadline = (start_time + timeout_seconds) if timeout_seconds is not None else None

    try:
        while True:
            try:
                process.wait(timeout=WAIT_POLL_INTERVAL_SECONDS)
                break
            except TimeoutException:
                if deadline and time.monotonic() >= deadline:
                    timed_out = True
                    logger.warning(f"{provider_name} timed out after {timeout_seconds}s, sending SIGTERM")
                    _force_kill(process, provider_name)
                    break
                if abort_event and abort_event.is_set():
                    aborted_during_wait = True
                    logger.info(f"{provider_name} aborting (abort event set)")
                    _force_kill(process, provider_name)
                    break
            except Exception as wait_error:
                logger.debug(f"{provider_name} wait interrupted: {type(wait_error).__name__}")
                _force_kill(process, provider_name)
                if abort_event and abort_event.is_set():
                    aborted_during_wait = True
                break
    finally:
        if running_processes is not None:
            with process_lock:
                running_processes.pop(provider_name, None)
        if stop_polling:
            stop_polling.set()
        if poll_thread:
            poll_thread.join(timeout=5)
            if poll_thread.is_alive():
                logger.warning(f"{provider_name} poll thread did not stop cleanly")

    latency_seconds = round(time.monotonic() - start_time, 2)

    stdout_log_path = Path(stdout_log)
    try:
        raw_stdout = stdout_log_path.read_text(encoding="utf-8", errors="replace") if stdout_log_path.stat().st_size > 0 else ""
    except (FileNotFoundError, OSError):
        raw_stdout = ""

    response_text = ANSI_ESCAPE_PATTERN.sub("", raw_stdout).replace("\r\n", "\n").strip()

    if not response_text:
        logger.debug(f"{provider_name} stdout empty, falling back to stderr log")
        stderr_log_path = Path(stderr_log)
        try:
            raw_stderr = stderr_log_path.read_text(encoding="utf-8", errors="replace")
            response_text = ANSI_ESCAPE_PATTERN.sub("", raw_stderr).replace("\r\n", "\n").strip()
        except (FileNotFoundError, OSError):
            pass

    if timed_out:
        exit_code = -1
        status = "timeout"
        if not response_text:
            response_text = f"TIMEOUT: Provider exceeded {timeout_seconds}s limit"
    elif aborted_during_wait:
        exit_code = -2
        status = "aborted"
    else:
        exit_code = process.exit_code if process.exit_code is not None else -4
        status = "success" if exit_code == 0 else "failed"

    log_level = logging.INFO if exit_code == 0 else logging.WARNING
    logger.log(log_level, f"{provider_name} {status} (exit_code={exit_code}) in {latency_seconds}s")

    return (provider_name, {
        "response": response_text,
        "exit_code": exit_code,
        "latency_seconds": latency_seconds,
        "status": status,
        "logs": {"stdout": stdout_log, "stderr": stderr_log},
    })


def _retry_launch_and_collect(command, provider_config: dict, prompt: str,
                              stdout_log: str, stderr_log: str,
                              timeout_seconds: int = None, working_directory: str = None,
                              streaming_buffer: deque = None, abort_event: threading.Event = None,
                              running_processes: dict = None, process_lock: threading.Lock = None,
                              max_retries: int = 0, model_override: str = None) -> tuple:
    """Retry wrapper around _launch_and_collect with exponential backoff. Tracks all attempts."""
    provider_name = provider_config["name"]
    all_attempts = []
    max_retries = max(0, max_retries)

    for attempt in range(max_retries + 1):
        if attempt > 0:
            backoff_seconds = min(2 ** (attempt - 1), 30)
            logger.info(f"{provider_name} retry {attempt}/{max_retries} after {backoff_seconds}s backoff")
            if abort_event and abort_event.wait(timeout=backoff_seconds):
                aborted_result = {
                    "response": "", "exit_code": -2, "latency_seconds": 0,
                    "status": "aborted",
                    "logs": {"stdout": stdout_log, "stderr": stderr_log},
                    "attempts": all_attempts,
                }
                return (provider_name, aborted_result)
            if streaming_buffer is not None:
                streaming_buffer.clear()

        if abort_event and abort_event.is_set():
            aborted_result = {
                "response": "", "exit_code": -2, "latency_seconds": 0,
                "status": "aborted",
                "logs": {"stdout": stdout_log, "stderr": stderr_log},
                "attempts": all_attempts,
            }
            return (provider_name, aborted_result)

        if attempt > 0:
            stdout_path = Path(stdout_log)
            stderr_path = Path(stderr_log)
            attempt_stdout = str(stdout_path.parent / f"{stdout_path.stem}_attempt{attempt}{stdout_path.suffix}")
            attempt_stderr = str(stderr_path.parent / f"{stderr_path.stem}_attempt{attempt}{stderr_path.suffix}")
        else:
            attempt_stdout = stdout_log
            attempt_stderr = stderr_log

        try:
            result = _launch_and_collect(
                command, provider_config, prompt, attempt_stdout, attempt_stderr,
                timeout_seconds=timeout_seconds, working_directory=working_directory,
                streaming_buffer=streaming_buffer, abort_event=abort_event,
                running_processes=running_processes, process_lock=process_lock,
                model_override=model_override,
            )
            name, result_data = result
        except Exception as launch_error:
            logger.warning(f"{provider_name} launch raised {type(launch_error).__name__}: {launch_error}")
            name = provider_name
            result_data = {
                "response": str(launch_error), "exit_code": -4, "latency_seconds": 0,
                "status": "error",
                "logs": {"stdout": attempt_stdout, "stderr": attempt_stderr},
            }
        all_attempts.append({
            "attempt": attempt + 1,
            "exit_code": result_data["exit_code"],
            "status": result_data["status"],
            "latency_seconds": result_data["latency_seconds"],
            "logs": result_data["logs"],
        })

        if result_data["exit_code"] == 0:
            result_data["attempts"] = all_attempts
            return (name, result_data)

        if attempt < max_retries:
            logger.warning(f"{provider_name} attempt {attempt + 1}/{max_retries + 1} failed "
                           f"(exit_code={result_data['exit_code']}), will retry")

    result_data["attempts"] = all_attempts
    return (name, result_data)


def _execute_providers(provider_configs: list, launch_provider_fn, fail_fast: bool,
                       ignore_errors: bool, abort_event: threading.Event,
                       running_processes: dict, process_lock: threading.Lock = None,
                       stream_update_fn=None, display_names: dict = None) -> tuple:
    """Execute providers in parallel, handling fail-fast. Returns (results_dict, failure_summary_list)."""
    if process_lock is None:
        process_lock = threading.RLock()
    results = {}
    failure_summary = []

    if not provider_configs:
        return results, failure_summary

    def _display(raw_name: str) -> str:
        return (display_names or {}).get(raw_name, raw_name)

    executor = ThreadPoolExecutor(max_workers=len(provider_configs))
    try:
        futures_map = {
            executor.submit(launch_provider_fn, provider_config): provider_config["name"]
            for provider_config in provider_configs
        }

        collected_futures = set()

        if fail_fast:
            for future in as_completed(futures_map):
                collected_futures.add(future)
                if stream_update_fn:
                    stream_update_fn()
                try:
                    name, result_data = future.result()
                except Exception as worker_error:
                    name = _display(futures_map[future])
                    logger.warning(f"{name} worker raised {type(worker_error).__name__}: {worker_error}")
                    result_data = {
                        "response": "", "exit_code": -4, "latency_seconds": 0,
                        "status": "error", "logs": {"stdout": "", "stderr": ""},
                    }
                results[name] = result_data
                if result_data["exit_code"] != 0 and result_data.get("status") != "aborted":
                    if not ignore_errors:
                        failure_summary.append(f"{name}: exit_code={result_data['exit_code']}")
                    logger.warning(f"{name} failed, aborting remaining providers (--fail-fast)")
                    abort_event.set()
                    with process_lock:
                        snapshot = list(running_processes.items())
                    for process_name, process_handle in snapshot:
                        _force_kill(process_handle, process_name)
                    break

            uncollected = {f for f in futures_map if f not in collected_futures}
            if uncollected:
                done_remaining, not_done = futures_wait(uncollected, timeout=30)
                for future in done_remaining:
                    try:
                        collected_name, collected_data = future.result()
                        results[collected_name] = collected_data
                    except Exception as collection_error:
                        fname = _display(futures_map[future])
                        logger.warning(f"{fname} result collection failed: {type(collection_error).__name__}")
                        results[fname] = {
                            "response": "", "exit_code": -3, "latency_seconds": 0,
                            "status": "collection_timeout", "logs": {"stdout": "", "stderr": ""},
                        }
                for future in not_done:
                    fname = _display(futures_map[future])
                    logger.warning(f"{fname} did not complete within collection timeout")
                    results[fname] = {
                        "response": "", "exit_code": -3, "latency_seconds": 0,
                        "status": "collection_timeout", "logs": {"stdout": "", "stderr": ""},
                    }
        else:
            remaining_futures = set(futures_map.keys())
            while remaining_futures:
                done_futures, remaining_futures = futures_wait(remaining_futures, timeout=0.15)
                if stream_update_fn:
                    stream_update_fn()
                for future in done_futures:
                    try:
                        name, result_data = future.result()
                    except Exception as worker_error:
                        name = _display(futures_map[future])
                        logger.warning(f"{name} worker raised {type(worker_error).__name__}: {worker_error}")
                        result_data = {
                            "response": "", "exit_code": -4, "latency_seconds": 0,
                            "status": "error", "logs": {"stdout": "", "stderr": ""},
                        }
                    results[name] = result_data
                    if result_data["exit_code"] != 0 and not ignore_errors:
                        failure_summary.append(f"{name}: exit_code={result_data['exit_code']}")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        with process_lock:
            stragglers = list(running_processes.items())
        for straggler_name, straggler_handle in stragglers:
            _force_kill(straggler_handle, straggler_name)

    return results, failure_summary


def _build_streaming_display(provider_configs: list, display_names: dict = None):
    """Return a function that builds a rich Group of Panels from shared streaming state."""
    from rich.console import Group as RichGroup
    from rich.panel import Panel
    from rich.text import Text

    provider_names = [
        display_names[pc["name"]] if display_names else pc["name"]
        for pc in provider_configs
    ]

    status_indicators = {
        "pending": ("\u2026", "dim"),
        "running": ("\u25cf", "yellow"),
        "success": ("\u2713", "green"),
        "failed": ("\u2717", "red"),
        "timeout": ("\u23f1", "red"),
        "aborted": ("\u2298", "dim"),
    }

    def make_display(buffers: dict, statuses: dict, latencies: dict):
        panels = []
        for name in provider_names:
            status = statuses[name]
            latency_string = f" {latencies[name]:.1f}s" if latencies[name] is not None else ""
            indicator, style = status_indicators.get(status, ("?", "white"))
            title = f"{name} [{indicator}{latency_string}]"

            # DESIGN: list() creates an atomic snapshot of the deque under CPython's GIL,
            # preventing RuntimeError from concurrent poll thread appends. This function is
            # called under streaming_lock from update_display(). The poll thread appends
            # without streaming_lock (deque.append is GIL-atomic), which is safe because
            # list(deque) only needs a consistent snapshot, not mutual exclusion.
            all_text = "".join(list(buffers.get(name, [])))
            lines = all_text.split("\n")
            visible_lines = lines[-STREAM_PANEL_HEIGHT:] if len(lines) > STREAM_PANEL_HEIGHT else lines
            content = "\n".join(visible_lines) or " "

            panels.append(Panel(
                Text.from_ansi(content, overflow="ellipsis", no_wrap=False),
                title=title,
                border_style=style,
                height=STREAM_PANEL_HEIGHT + 2,
                expand=True,
            ))

        return RichGroup(*panels)

    return make_display


def run_hydra(prompt: str, provider_names: list = None, log_base_directory: str = LOG_BASE_DIR,
              timeout_seconds: int = None, working_directory: str = None,
              fail_fast: bool = False, ignore_errors: bool = False,
              retries: int = 0, stream: bool = False,
              preflight: bool = True, ping_timeout: int = PREFLIGHT_PING_TIMEOUT_SECONDS,
              model_overrides: dict = None) -> str:
    """Run selected providers in parallel with the given prompt. Returns JSON string."""
    logger.debug(f"run_hydra called with provider_names={provider_names} log_base_directory={log_base_directory}")

    prompt_byte_size = len(prompt.encode("utf-8"))
    if prompt_byte_size > MAX_PROMPT_ARG_BYTES:
        raise HydraError(
            f"Prompt is {prompt_byte_size:,} bytes, exceeding OS argument limit "
            f"of {MAX_PROMPT_ARG_BYTES:,} bytes (128KB). Use a shorter prompt or "
            f"--prompt-file with a provider that supports stdin."
        )

    if not provider_names:
        provider_names = list_providers()

    seen = set()
    provider_names = [n for n in provider_names if n not in seen and not seen.add(n)]

    logger.info(f"Providers: {', '.join(provider_names)}")
    logger.info(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    if timeout_seconds is not None:
        logger.info(f"Timeout: {timeout_seconds}s per provider")
    if working_directory:
        working_directory = str(Path(working_directory).resolve())
        if not Path(working_directory).is_dir():
            raise HydraError(f"Working directory does not exist: {working_directory}")
        logger.info(f"Working directory: {working_directory}")
    if retries:
        logger.info(f"Retries: {retries} per provider")

    try:
        provider_configs = [get_provider(name) for name in provider_names]
    except KeyError as key_error:
        raise HydraError(str(key_error)) from None
    commands = {}
    skipped_providers = []
    for provider_config in provider_configs:
        try:
            commands[provider_config["name"]] = _resolve_command(provider_config)
        except HydraError:
            if ignore_errors:
                logger.warning(f"Skipping {provider_config['name']}: binary not found (--ignore-errors)")
                skipped_providers.append(provider_config["name"])
            else:
                raise
    provider_configs = [pc for pc in provider_configs if pc["name"] not in skipped_providers]
    provider_names = [name for name in provider_names if name not in skipped_providers]

    if not provider_configs:
        raise HydraError("No providers available to run (all skipped or missing)")

    abort_event = threading.Event()
    running_processes = {}
    process_lock = threading.RLock()

    is_main_thread = threading.current_thread() is threading.main_thread()
    _SIGINT_NOT_SET = object()
    original_sigint_handler = _SIGINT_NOT_SET

    if is_main_thread:
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        sigint_received = [False]

        def sigint_handler(signum, frame):
            # DESIGN: No lock acquisition here. Signal handlers run between bytecodes on the
            # main thread. Acquiring process_lock would deadlock if a worker thread holds it.
            # list(dict.values()) is GIL-atomic in CPython. Sending SIGTERM to a stale PID is
            # harmless (_kill_process_group catches ProcessLookupError). The abort_event causes
            # worker threads to do proper cleanup via _force_kill with SIGKILL escalation.
            if sigint_received[0]:
                os.write(2, b"hydra-heads: Second SIGINT, force exiting\n")
                signal.signal(signal.SIGINT, original_sigint_handler)
                raise KeyboardInterrupt
            sigint_received[0] = True
            os.write(2, b"hydra-heads: Received SIGINT, aborting all providers...\n")
            abort_event.set()
            for process_handle in list(running_processes.values()):
                _kill_process_group(process_handle.pid, signal.SIGTERM)

        signal.signal(signal.SIGINT, sigint_handler)

    try:
        if preflight and provider_configs:
            provider_configs = _preflight_ping(
                provider_configs, commands, log_base_directory, ping_timeout,
                abort_event=abort_event, running_processes=running_processes,
                process_lock=process_lock,
            )
            provider_names = [pc["name"] for pc in provider_configs]

        display_names = {}
        for provider_config in provider_configs:
            pname = provider_config["name"]
            provider_model_override = (model_overrides or {}).get(pname)
            detected_model = _detect_model(provider_config, model_override=provider_model_override)
            display_names[pname] = _make_display_name(pname, detected_model)
        logger.info(f"Display names: {', '.join(display_names.values())}")

        display_name_list = [display_names[pc["name"]] for pc in provider_configs]
        task_directory = _prepare_task_directory(log_base_directory, prompt)
        log_paths = _prepare_log_paths(task_directory, display_name_list)

        streaming_buffers = {display_names[pc["name"]]: deque(maxlen=STREAM_BUFFER_MAX_CHUNKS) for pc in provider_configs} if stream else None
        streaming_statuses = {display_names[pc["name"]]: "pending" for pc in provider_configs} if stream else None
        streaming_latencies = {display_names[pc["name"]]: None for pc in provider_configs} if stream else None
        streaming_lock = threading.Lock() if stream else None

        def launch_provider(provider_config: dict) -> tuple:
            name = provider_config["name"]
            dname = display_names[name]
            buffer = streaming_buffers[dname] if streaming_buffers else None

            if streaming_statuses:
                with streaming_lock:
                    streaming_statuses[dname] = "running"

            provider_model_override = (model_overrides or {}).get(name)
            result_name, result_data = _retry_launch_and_collect(
                commands[name], provider_config, prompt,
                log_paths[f"{dname}_stdout"], log_paths[f"{dname}_stderr"],
                timeout_seconds=timeout_seconds, working_directory=working_directory,
                streaming_buffer=buffer, abort_event=abort_event,
                running_processes=running_processes, process_lock=process_lock,
                max_retries=retries, model_override=provider_model_override,
            )

            if streaming_statuses:
                with streaming_lock:
                    streaming_statuses[dname] = result_data.get("status", "unknown")
                    streaming_latencies[dname] = result_data.get("latency_seconds")

            return (dname, result_data)

        if stream:
            from rich.console import Console
            from rich.live import Live

            make_display = _build_streaming_display(provider_configs, display_names)
            console = Console(stderr=True)

            with Live(
                make_display(streaming_buffers, streaming_statuses, streaming_latencies),
                refresh_per_second=4,
                console=console,
            ) as live:
                def update_display():
                    with streaming_lock:
                        live.update(make_display(streaming_buffers, streaming_statuses, streaming_latencies))

                results, failure_summary = _execute_providers(
                    provider_configs, launch_provider, fail_fast, ignore_errors,
                    abort_event, running_processes, process_lock=process_lock,
                    stream_update_fn=update_display, display_names=display_names,
                )
                update_display()
        else:
            results, failure_summary = _execute_providers(
                provider_configs, launch_provider, fail_fast, ignore_errors,
                abort_event, running_processes, process_lock=process_lock,
                display_names=display_names,
            )
    finally:
        if is_main_thread and original_sigint_handler is not _SIGINT_NOT_SET:
            signal.signal(signal.SIGINT, original_sigint_handler)

    if failure_summary and not ignore_errors:
        logger.warning(f"Provider failures: {'; '.join(failure_summary)}")

    logger.info("All providers completed")
    logger.debug(f"run_hydra returning {len(results)} results")
    return json.dumps(results, indent=2)
