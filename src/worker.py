"""Streaming chat completion worker."""

import json

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from constants import DEFAULT_SERVER_BASE_URL

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

    def configure(self, base_url, model_name, messages, temperature, top_p, top_k):
        self.base_url = base_url
        self.model_name = model_name
        self.messages = messages
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k

    def run(self):
        self.stop_requested = False
        self.full_response = ""
        self.full_thinking = ""
        self.generation_started.emit()

        payload = {
            "model": self.model_name,
            "messages": self.messages,
            "stream": True,
            "max_tokens": 1024,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        success = False
        stopped = False

        try:
            chat_url = f"{self.base_url}/v1/chat/completions"
            with requests.post(chat_url, json=payload, stream=True, timeout=120) as response:
                if response.status_code != 200:
                    detail = response.text.strip() or f"HTTP {response.status_code}"
                    self.error_occurred.emit(f"Request failed: {detail}")
                    self.generation_finished.emit(False, False, self.full_response, self.full_thinking)
                    return

                for line in response.iter_lines():
                    if self.stop_requested:
                        stopped = True
                        break
                    if not line:
                        continue
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="ignore")
                    if not line.startswith("data: "):
                        continue
                    line = line[6:]
                    if line == "[DONE]":
                        success = True
                        break
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
                        self.full_response += token
                        self.token_received.emit(token)
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(f"OpenAI-compatible server is not reachable at {self.base_url}.")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("The request timed out.")
        except Exception as exc:
            self.error_occurred.emit(f"Unexpected error: {exc}")

        self.generation_finished.emit(success, stopped, self.full_response, self.full_thinking)

    def stop(self):
        self.stop_requested = True
