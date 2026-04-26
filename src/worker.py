"""Streaming chat completion worker."""

import base64
import json
import ntpath
import os
import queue
import selectors
import shlex
import signal
import subprocess
import threading
import time

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from constants import (
    APP_WORKSPACE,
    DEFAULT_SERVER_BASE_URL,
    IS_WINDOWS,
    MAX_AGENT_TERMINAL_STEPS,
    TERMINAL_COMMAND_RE,
    TERMINAL_OUTPUT_LIMIT,
    TERMINAL_SHELL_NAME,
    TERMINAL_TIMEOUT_SECONDS,
)

class ChatCompletionWorker(QThread):
    token_received = pyqtSignal(str)
    thinking_received = pyqtSignal(str)
    terminal_command_started = pyqtSignal(str, str)
    terminal_log_received = pyqtSignal(str)
    terminal_command_finished = pyqtSignal(str)
    terminal_permission_requested = pyqtSignal(str, str)
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal(bool, bool, str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stop_requested = False
        self.base_url = DEFAULT_SERVER_BASE_URL
        self.messages = []
        self.model_name = ""
        self.temperature = 0.7
        self.top_p = 0.9
        self.top_k = 40
        self.full_response = ""
        self.full_thinking = ""
        self.agent_terminal_enabled = False
        self.agent_terminal_permission = "default"
        self.default_permissions = set()
        self.terminal_cwd = APP_WORKSPACE
        self.permission_condition = threading.Condition()
        self.pending_permission_decision = None

    def configure(
        self,
        base_url,
        model_name,
        messages,
        temperature,
        top_p,
        top_k,
        agent_terminal_enabled=False,
        agent_terminal_permission="default",
        default_permissions=None,
        terminal_cwd=None,
    ):
        self.base_url = base_url
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.agent_terminal_enabled = bool(agent_terminal_enabled)
        self.agent_terminal_permission = agent_terminal_permission
        self.default_permissions = {
            self.normalize_terminal_command_key(command)
            for command in (default_permissions or [])
            if self.normalize_terminal_command_key(command)
        }
        self.terminal_cwd = terminal_cwd or APP_WORKSPACE

    def run(self):
        self.stop_requested = False
        self.full_response = ""
        self.full_thinking = ""
        self.generation_started.emit()

        success = False
        stopped = False

        try:
            messages = list(self.messages)
            for step in range(MAX_AGENT_TERMINAL_STEPS + 1):
                response_text, generation_success, stopped = self.stream_chat_completion(messages)
                if not generation_success or stopped:
                    success = generation_success
                    break

                command = self.extract_terminal_command(response_text)
                if not self.agent_terminal_enabled or not command:
                    success = True
                    break

                approval = self.terminal_command_approval(command)
                if approval == "reject":
                    if self.stop_requested:
                        stopped = True
                        break
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "The requested terminal command was dismissed by the user and was not run:\n\n"
                                f"```terminal\n$ {command}\n[dismissed]\n```\n\n"
                                "Continue without running that command. If you can answer from existing context, do so."
                            ),
                        }
                    )
                    continue

                self.terminal_command_started.emit(command, TERMINAL_SHELL_NAME)
                terminal_result = self.run_terminal_command(command)
                rendered_result = self.render_terminal_result(command, terminal_result)
                self.terminal_command_finished.emit(self.terminal_status_text(terminal_result))
                if self.stop_requested:
                    stopped = True
                    break

                messages.append({"role": "assistant", "content": response_text})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Terminal output for the command you requested:\n\n"
                            f"{rendered_result}\n\n"
                            "Continue. If you need another command, use one terminal_command tag. "
                            "If you are done, answer normally without a terminal_command tag."
                        ),
                    }
                )

                if step == MAX_AGENT_TERMINAL_STEPS:
                    limit_message = "\n\n_Agent terminal step limit reached._"
                    self.full_response += limit_message
                    self.token_received.emit(limit_message)
                    success = True
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(f"OpenAI-compatible server is not reachable at {self.base_url}.")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("The request timed out.")
        except Exception as exc:
            self.error_occurred.emit(f"Unexpected error: {exc}")

        self.generation_finished.emit(success, stopped, self.full_response, self.full_thinking)

    def stop(self):
        self.stop_requested = True
        self.resolve_terminal_permission("reject")

    def stream_chat_completion(self, messages):
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }
        response_text = ""
        chat_url = f"{self.base_url}/v1/chat/completions"
        with requests.post(chat_url, json=payload, stream=True, timeout=120) as response:
            if response.status_code != 200:
                detail = response.text.strip() or f"HTTP {response.status_code}"
                self.error_occurred.emit(f"Request failed: {detail}")
                return response_text, False, False

            for line in response.iter_lines():
                if self.stop_requested:
                    return response_text, False, True
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="ignore")
                if not line.startswith("data: "):
                    continue
                line = line[6:]
                if line == "[DONE]":
                    return response_text, True, False
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                delta = data.get("choices", [{}])[0].get("delta", {})
                thinking = delta.get("reasoning_content", "")
                if thinking:
                    self.full_thinking += thinking
                    self.thinking_received.emit(thinking)
                token = delta.get("content", "")
                if token:
                    response_text += token
                    self.full_response += token
                    self.token_received.emit(token)
        return response_text, False, False

    def extract_terminal_command(self, text):
        match = TERMINAL_COMMAND_RE.search(text or "")
        if not match:
            return ""
        return (match.group(1) or match.group(2) or "").strip()

    def terminal_command_key(self, command):
        if IS_WINDOWS:
            return self.windows_terminal_command_key(command)
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        if not parts:
            return ""
        return os.path.basename(parts[0])

    def windows_terminal_command_key(self, command):
        command = (command or "").lstrip()
        if not command:
            return ""
        for operator in ("&", "."):
            if command == operator:
                return ""
            if command.startswith(operator) and command[1:2].isspace():
                command = command[1:].lstrip()
                break
        token = self.windows_terminal_first_token(command)
        if not token:
            return ""
        return ntpath.basename(token.rstrip("\\/"))

    def windows_terminal_first_token(self, command):
        quote = command[:1]
        if quote in ("'", '"'):
            token = []
            index = 1
            while index < len(command):
                char = command[index]
                if char == "`" and index + 1 < len(command):
                    token.append(command[index + 1])
                    index += 2
                    continue
                if char == quote:
                    return "".join(token)
                token.append(char)
                index += 1
            return "".join(token)
        return command.split(maxsplit=1)[0].strip("'\"")

    def normalize_terminal_command_key(self, command_key):
        command_key = str(command_key or "").strip()
        if IS_WINDOWS:
            return command_key.lower()
        return command_key

    def terminal_command_approval(self, command):
        if self.agent_terminal_permission == "full_access":
            return "allow"
        command_key = self.terminal_command_key(command)
        permission_key = self.normalize_terminal_command_key(command_key)
        if permission_key and permission_key in self.default_permissions and not self.command_has_shell_control(command):
            return "allow"
        return self.wait_for_terminal_permission(command, command_key)

    def command_has_shell_control(self, command):
        control_tokens = ("&&", "||", ";", "|", ">", "<", "`", "$(", "\n", "\r")
        return any(token in command for token in control_tokens)

    def wait_for_terminal_permission(self, command, command_key):
        with self.permission_condition:
            self.pending_permission_decision = None
        self.terminal_permission_requested.emit(command, command_key)
        with self.permission_condition:
            while self.pending_permission_decision is None and not self.stop_requested:
                self.permission_condition.wait(timeout=0.1)
            decision = self.pending_permission_decision or "reject"
            self.pending_permission_decision = None
        if decision == "allow_always" and command_key:
            self.default_permissions.add(self.normalize_terminal_command_key(command_key))
            return "allow"
        if decision == "allow_once":
            return "allow"
        return "reject"

    def resolve_terminal_permission(self, decision):
        with self.permission_condition:
            self.pending_permission_decision = decision
            self.permission_condition.notify_all()

    def run_terminal_command(self, command):
        if IS_WINDOWS:
            return self.run_windows_terminal_command(command)
        return self.run_posix_terminal_command(command)

    def run_posix_terminal_command(self, command):
        process = None
        selector = None
        output_parts = []
        try:
            process = subprocess.Popen(
                ["/bin/bash", "-lc", command],
                cwd=str(self.terminal_cwd),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            selector = selectors.DefaultSelector()
            if process.stdout is not None:
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            if process.stderr is not None:
                os.set_blocking(process.stderr.fileno(), False)
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")

            deadline = time.monotonic() + TERMINAL_TIMEOUT_SECONDS
            while process.poll() is None or selector.get_map():
                if self.stop_requested:
                    self.terminate_terminal_process(process)
                    self.terminal_log_received.emit("\n[stopped]\n")
                    return {
                        "exit_code": None,
                        "timed_out": False,
                        "stopped": True,
                        "output": self.truncate_terminal_output("".join(output_parts).strip() or "Terminal command stopped."),
                    }
                if time.monotonic() >= deadline:
                    self.terminate_terminal_process(process, force=True)
                    return {
                        "exit_code": None,
                        "timed_out": True,
                        "stopped": False,
                        "output": self.truncate_terminal_output("".join(output_parts).strip()),
                    }

                events = selector.select(timeout=0.1)
                if not events and process.poll() is not None:
                    break
                for key, _events in events:
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        try:
                            selector.unregister(key.fileobj)
                        except Exception:
                            pass
                        continue
                    text = chunk.decode("utf-8", errors="replace")
                    if key.data == "stderr":
                        text = f"[stderr] {text}"
                    output_parts.append(text)
                    self.terminal_log_received.emit(text)

            return {
                "exit_code": process.returncode,
                "timed_out": False,
                "stopped": False,
                "output": self.truncate_terminal_output("".join(output_parts).strip()),
            }
        except Exception as exc:
            if process is not None and process.poll() is None:
                self.terminate_terminal_process(process, force=True)
            return {
                "exit_code": None,
                "timed_out": False,
                "stopped": False,
                "output": f"Unable to run terminal command: {exc}",
            }
        finally:
            if selector is not None:
                selector.close()

    def run_windows_terminal_command(self, command):
        process = None
        output_queue = queue.Queue()
        reader_threads = []
        try:
            encoded_command = self.windows_powershell_encoded_command(command)
            process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    encoded_command,
                ],
                cwd=str(self.terminal_cwd),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )

            for stream_name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                if stream is None:
                    continue
                thread = threading.Thread(
                    target=self.read_windows_terminal_stream,
                    args=(stream_name, stream, output_queue),
                    daemon=True,
                )
                thread.start()
                reader_threads.append(thread)

            output_parts = []
            deadline = time.monotonic() + TERMINAL_TIMEOUT_SECONDS
            while process.poll() is None or any(thread.is_alive() for thread in reader_threads):
                if self.stop_requested:
                    self.terminate_terminal_process(process)
                    self.drain_windows_terminal_output(output_queue, output_parts)
                    self.terminal_log_received.emit("\n[stopped]\n")
                    return {
                        "exit_code": None,
                        "timed_out": False,
                        "stopped": True,
                        "output": self.truncate_terminal_output("".join(output_parts).strip() or "Terminal command stopped."),
                    }
                if time.monotonic() >= deadline:
                    self.terminate_terminal_process(process, force=True)
                    self.drain_windows_terminal_output(output_queue, output_parts)
                    return {
                        "exit_code": None,
                        "timed_out": True,
                        "stopped": False,
                        "output": self.truncate_terminal_output("".join(output_parts).strip()),
                    }

                try:
                    stream_name, chunk = output_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self.append_windows_terminal_output(stream_name, chunk, output_parts)

            self.drain_windows_terminal_output(output_queue, output_parts)
            if self.stop_requested:
                return {
                    "exit_code": None,
                    "timed_out": False,
                    "stopped": True,
                    "output": self.truncate_terminal_output("".join(output_parts).strip() or "Terminal command stopped."),
                }
            return {
                "exit_code": process.returncode,
                "timed_out": False,
                "stopped": False,
                "output": self.truncate_terminal_output("".join(output_parts).strip()),
            }
        except Exception as exc:
            if process is not None and process.poll() is None:
                self.terminate_terminal_process(process, force=True)
            return {
                "exit_code": None,
                "timed_out": False,
                "stopped": False,
                "output": f"Unable to run terminal command: {exc}",
            }
        finally:
            for thread in reader_threads:
                thread.join(timeout=0.2)

    def windows_powershell_encoded_command(self, command):
        script = (
            "$__acuEncoding = [System.Text.UTF8Encoding]::new($false)\n"
            "[Console]::OutputEncoding = $__acuEncoding\n"
            "[Console]::InputEncoding = $__acuEncoding\n"
            "$OutputEncoding = $__acuEncoding\n"
            f"{command}"
        )
        return base64.b64encode(script.encode("utf-16le")).decode("ascii")

    def read_windows_terminal_stream(self, stream_name, stream, output_queue):
        try:
            while True:
                chunk = os.read(stream.fileno(), 4096)
                if not chunk:
                    break
                output_queue.put((stream_name, chunk))
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def append_windows_terminal_output(self, stream_name, chunk, output_parts):
        text = chunk.decode("utf-8", errors="replace")
        if stream_name == "stderr":
            text = f"[stderr] {text}"
        output_parts.append(text)
        self.terminal_log_received.emit(text)

    def drain_windows_terminal_output(self, output_queue, output_parts):
        while True:
            try:
                stream_name, chunk = output_queue.get_nowait()
            except queue.Empty:
                break
            self.append_windows_terminal_output(stream_name, chunk, output_parts)

    def terminate_terminal_process(self, process, force=False):
        if IS_WINDOWS:
            try:
                if force:
                    process.kill()
                else:
                    process.terminate()
                process.wait(timeout=1)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            return
        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        except Exception:
            process.kill()
        try:
            process.wait(timeout=1)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def truncate_terminal_output(self, output):
        if not output:
            return "(no output)"
        if len(output) <= TERMINAL_OUTPUT_LIMIT:
            return output
        return output[:TERMINAL_OUTPUT_LIMIT] + "\n\n[Terminal output truncated]"

    def render_terminal_result(self, command, result):
        status = self.terminal_status_text(result)
        return (
            "\n\n```terminal\n"
            f"$ {command}\n"
            f"[{status}]\n"
            f"{result['output']}\n"
            "```\n\n"
        )

    def terminal_status_text(self, result):
        if result.get("timed_out"):
            return "timed out"
        if result.get("stopped"):
            return "stopped"
        if result.get("exit_code") is None:
            return "failed"
        return f"exit code {result['exit_code']}"
