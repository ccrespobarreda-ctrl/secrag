"""
The generation layer, behind an interface.

    provider = get_provider()
    answer = provider.complete(system=..., user=...)

WHY AN INTERFACE FOR A SINGLE CALL

The clients who most need retrieval over their own documents are the ones who
cannot send those documents to a third-party API: law firms, clinics, banks,
anyone under data-residency obligations. For them the question is not how good
the model is, it is whether the data leaves the network.

With this interface the answer is a configuration change rather than a rewrite,
and the claim in the README is true rather than aspirational:

    The retrieval layer runs entirely on-premise. Only the generation call
    crosses the network, and it sits behind a provider interface that can be
    swapped for a local model.

Without the interface that sentence would be a lie, which is why half an hour
spent here is worth it.

A NOTE ON DETERMINISM

Both providers originally passed temperature=0, so that the same question with
the same excerpts would give the same answer and the evaluation would measure the
system rather than sampling noise. Current models reject the parameter:

    400 invalid_request_error: `temperature` is deprecated for this model

It is not set. That means repeated runs of the same question can differ, and the
evaluation harness has to account for it: a refusal rate measured once is a
sample, not a constant. The results page states the number of runs behind each
figure for that reason.

THE DEFAULT IS SAFE, WHICH IS WHY IT HAD TO BE LOUD

LLM_PROVIDER defaults to echo, and that is right: a missing variable should not
start spending money. But nothing in this project loaded .env, so a session that
had not run load-env.ps1 resolved to echo while .env plainly said anthropic --
and an evaluation then ran end to end without calling a model.

What it produces in that state is the problem. Echo refuses everything, so the
run reports 100% refusal on unanswerable questions and 0% hallucination: the most
flattering possible values on the two figures this project leads with, obtained
by making no calls at all. It cost nothing and looked like a result.

Two changes. .env is loaded here, so the file that declares the provider is the
file that decides it. And the harness that spends money asks for the provider by
name -- see --require-provider in evaluate_generation.py -- so falling back to
echo fails the run instead of silently producing a perfect score.

WHAT IS DELIBERATELY NOT HERE

No prompt construction, no citation parsing, no retry-on-bad-output. Those belong
to generate.py, which owns what a good answer looks like. This module owns only
how bytes reach a model and come back.
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C  # noqa: E402


log = logging.getLogger("llm")

# Loaded here rather than left to each caller. The provider is declared in .env;
# a caller that forgot to load it did not get an error, it got echo, and echo
# scores perfectly on the two headline metrics without calling anything.
#
# override=False on purpose: a variable already set in the shell beats the file,
# which is what makes `LLM_PROVIDER=echo python ...` work as a deliberate dry run.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv is optional; the variables may be exported
    pass

# Transient API failures, and how long to wait before deciding a run is lost.
#
# A 529 arrived partway through a 150-call evaluation and killed the whole run.
# The service was fine two seconds later; the harness was not built to notice
# that. Retrying is not optional in a batch this size: at 150 calls, an
# individual failure rate of even 1% makes a clean run unlikely.
MAX_ATTEMPTS = 5
BASE_BACKOFF = 2.0


def _with_retries(call, description: str = "request"):
    """
    Retry on overload, rate limits and server errors, with exponential backoff
    and jitter.

    Jitter matters when several calls fail together: without it they all wake at
    the same moment and hit the service in step, reproducing the overload they
    were waiting out.

    Authentication and bad-request errors are not retried. Those do not fix
    themselves, and repeating them wastes time and hides the real message.
    """
    import anthropic

    transient = (
        getattr(anthropic, "APIConnectionError", ()),
        getattr(anthropic, "APITimeoutError", ()),
        getattr(anthropic, "InternalServerError", ()),
        getattr(anthropic, "RateLimitError", ()),
    )
    transient = tuple(t for t in transient if isinstance(t, type))

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            retryable = isinstance(exc, transient) or status in (429, 500, 502, 503, 529)

            if not retryable or attempt == MAX_ATTEMPTS:
                raise

            wait = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 1)
            log.warning("%s failed (%s), attempt %d of %d, retrying in %.1fs",
                        description, type(exc).__name__, attempt, MAX_ATTEMPTS, wait)
            time.sleep(wait)


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int) -> str: ...


class VertexProvider:
    """
    Claude through Vertex AI.

    Vertex rather than the direct API because the deployment target is Google
    Cloud: one identity, one billing account, one audit trail. The model and the
    responses are the same.

    Verify against the current SDK documentation before trusting the import path
    and the region — both have changed, and model availability by region is
    limited.
    """

    name = "vertex"

    def __init__(self) -> None:
        from anthropic import AnthropicVertex

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        region = os.environ.get("GOOGLE_CLOUD_REGION", "europe-west1")
        if not project:
            raise SystemExit(
                "GOOGLE_CLOUD_PROJECT is not set. Vertex needs a project id and "
                "a region, and the model must be enabled in Model Garden for "
                "that region.")

        self.model = os.environ.get("GENERATION_MODEL") or C.GENERATION_MODEL
        if not self.model:
            raise SystemExit(
                "GENERATION_MODEL is not set. Model identifiers on Vertex differ "
                "from the direct API; take the exact string from Model Garden.")

        self.client = AnthropicVertex(project_id=project, region=region)

    def complete(self, system: str, user: str,
                 max_tokens: int = C.MAX_ANSWER_TOKENS) -> str:
        response = _with_retries(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ),
            description=f"{self.name} completion",
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text"
        )


class AnthropicProvider:
    """
    Claude through Anthropic's own API.

    Added because Vertex requires a billing account the project did not have,
    and waiting on an approval is worse than changing one line of configuration.
    That is the whole argument for the interface: the blocker moved the provider,
    not the system.

    Verify the model identifier against current documentation. Model names change
    and a stale one fails with a 404 that does not say which part is wrong.
    """

    name = "anthropic"

    def __init__(self) -> None:
        from anthropic import Anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set. Put it in .env, which is "
                "gitignored, and load it with load-env.ps1 -- never inline in a "
                "command, where it lands in shell history.")

        self.model = os.environ.get("GENERATION_MODEL") or C.GENERATION_MODEL
        if not self.model:
            raise SystemExit(
                "GENERATION_MODEL is not set. Take the exact identifier from the "
                "current API documentation.")

        self.client = Anthropic()

    def complete(self, system: str, user: str,
                 max_tokens: int = C.MAX_ANSWER_TOKENS) -> str:
        response = _with_retries(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ),
            description=f"{self.name} completion",
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", "") == "text"
        )


class LocalProvider:
    """
    Placeholder for a locally served model.

    Not implemented, and saying so is the point: an interface with one real
    implementation is honest, while an interface with a half-written second one
    invites a claim that cannot be demonstrated.

    The work is a client for whatever serves the model — llama.cpp, vLLM,
    Ollama — behind the same complete() signature. Nothing else in the system
    changes.
    """

    name = "local"

    def __init__(self) -> None:
        raise SystemExit(
            "The local provider is not implemented. LLM_PROVIDER=vertex is the "
            "working path; this class marks where a local model would attach.")

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        raise NotImplementedError


class EchoProvider:
    """
    Returns a fixed refusal without calling anything.

    Exists so the prompt builder, the citation parser and the evaluation plumbing
    can be exercised end to end without spending a single token. Every part of
    generate.py except the model itself is testable this way.
    """

    name = "echo"

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply or (
            f"{C.REFUSAL_MARKER}\nNo excerpts were provided to this provider.")

    def complete(self, system: str, user: str,
                 max_tokens: int = C.MAX_ANSWER_TOKENS) -> str:
        return self.reply


_PROVIDERS = {
    "anthropic": AnthropicProvider,
    "vertex": VertexProvider,
    "local": LocalProvider,
    "echo": EchoProvider,
}


def get_provider(name: str | None = None,
                 require: str | None = None) -> LLMProvider:
    """
    Resolve the provider, and optionally refuse to be a different one.

    `require` exists for the harnesses that spend money. Asking for anthropic and
    silently receiving echo is not a smaller version of the run; it is a
    different measurement that happens to score perfectly, and it has already
    happened once.
    """
    requested = name or os.environ.get("LLM_PROVIDER", "echo")
    resolved = requested.lower()
    if resolved not in _PROVIDERS:
        raise SystemExit(
            f"Unknown provider {resolved!r}. Options: {', '.join(_PROVIDERS)}")

    if require and resolved != require.lower():
        raise SystemExit(
            f"This run asked for provider {require!r} and resolved {resolved!r}.\n"
            f"LLM_PROVIDER is {os.environ.get('LLM_PROVIDER') or '(not set)'}, "
            f"and .env is read from the repository root.\n"
            f"Echo refuses every question, which scores 100% refusal and 0% "
            f"hallucination\nwithout calling anything. Stopping rather than "
            f"reporting that as a result.")

    return _PROVIDERS[resolved]()
