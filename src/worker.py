"""Streaming chat completion worker."""

import json
import os
import selectors
import signal
import subprocess
import time

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from constants import (
    APP_WORKSPACE,
    DEFAULT_SERVER_BASE_URL,
    MAX_AGENT_TERMINAL_STEPS,
    TERMINAL_COMMAND_RE,
    TERMINAL_OUTPUT_LIMIT,
    TERMINAL_TIMEOUT_SECONDS,
)

class ChatCompletionWorker(QThread):
    token_received = pyqtSignal(str)
    thinking_received = pyqtSignal(str)
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
        self.terminal_cwd = APP_WORKSPACE

    def configure(self, base_url, model_name, messages, temperature, top_p, top_k, agent_terminal_enabled=False):
        self.base_url = base_url
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.agent_terminal_enabled = bool(agent_terminal_enabled)

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

                terminal_result = self.run_terminal_command(command)
                rendered_result = self.render_terminal_result(command, terminal_result)
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

    def run_terminal_command(self, command):
        process = None
        selector = None
        output_parts = []
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.terminal_cwd),
                shell=True,
                executable="/bin/bash",
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

    def combine_terminal_streams(self, stdout, stderr):
        stdout = stdout or ""
        stderr = stderr or ""
        if stderr:
            return f"{stdout}\n[stderr]\n{stderr}" if stdout else f"[stderr]\n{stderr}"
        return stdout

    def terminate_terminal_process(self, process, force=False):
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
