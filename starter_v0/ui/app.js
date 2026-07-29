const chat = document.querySelector("#chat");
const form = document.querySelector("#composer");
const messageInput = document.querySelector("#message");
const sendButton = document.querySelector("#send");
const newTranscriptButton = document.querySelector("#newTranscript");
const template = document.querySelector("#turnTemplate");

const fields = {
  provider: document.querySelector("#provider"),
  model: document.querySelector("#model"),
  version: document.querySelector("#version"),
  artifact: document.querySelector("#artifact"),
  transcript: document.querySelector("#transcript"),
};

function setText(node, value) {
  node.textContent = value == null || value === "" ? "-" : String(value);
}

function asJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function summarizeResult(result) {
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    return result;
  }
  const summary = {};
  for (const key of ["error", "message", "status", "chars_returned", "question", "awaiting_user"]) {
    if (result[key] !== undefined && result[key] !== null) {
      summary[key] = result[key];
    }
  }
  if (Array.isArray(result.items)) {
    summary.item_count = result.items.length;
    summary.first_item = result.items[0] ?? null;
  }
  return summary;
}

function updateMeta(metadata) {
  setText(fields.provider, metadata.provider);
  setText(fields.model, metadata.model);
  setText(fields.version, metadata.version);
  setText(fields.artifact, metadata.artifact_version);
  setText(fields.transcript, metadata.transcript_path);
}

function emptyState() {
  if (chat.children.length > 0) return;
  const node = document.createElement("p");
  node.className = "empty";
  node.textContent = "Ask a question to test routing, tool args, tool results, and transcript logging.";
  chat.appendChild(node);
}

function removeEmptyState() {
  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();
}

function appendPre(parent, value) {
  const pre = document.createElement("pre");
  pre.textContent = asJson(value);
  parent.appendChild(pre);
}

function renderTrace(container, rounds) {
  container.replaceChildren();
  if (!rounds || rounds.length === 0) {
    const p = document.createElement("p");
    p.textContent = "No tool rounds.";
    container.appendChild(p);
    return;
  }

  for (const round of rounds) {
    const roundNode = document.createElement("section");
    roundNode.className = "round";

    const title = document.createElement("h3");
    title.textContent = `Round ${round.round}: ${(round.tool_calls || []).length} tool call(s)`;
    roundNode.appendChild(title);

    if (round.assistant_text) {
      const draft = document.createElement("p");
      draft.textContent = round.assistant_text;
      roundNode.appendChild(draft);
    }

    (round.tool_calls || []).forEach((call, index) => {
      const tool = document.createElement("div");
      tool.className = "tool";

      const name = document.createElement("div");
      name.className = "tool-name";
      name.textContent = `${index + 1}. ${call.name}`;
      tool.appendChild(name);

      appendPre(tool, call.args || {});
      const result = (round.tool_results || [])[index];
      if (result) {
        appendPre(tool, summarizeResult(result.result));
      }

      roundNode.appendChild(tool);
    });

    container.appendChild(roundNode);
  }
}

function renderTurn(turn) {
  removeEmptyState();
  const fragment = template.content.cloneNode(true);
  const node = fragment.querySelector(".turn");
  const userBubble = fragment.querySelector(".user");
  const answer = fragment.querySelector(".answer");
  const rounds = fragment.querySelector(".rounds");

  userBubble.textContent = turn.user || "";
  if (turn.status === "provider_error") {
    answer.classList.add("error");
    answer.textContent = turn.error || "Provider error";
  } else {
    answer.textContent = turn.assistant_text || "";
  }
  renderTrace(rounds, turn.rounds || []);

  chat.appendChild(fragment);
  node?.scrollIntoView({ behavior: "smooth", block: "end" });
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

async function loadMetadata() {
  const response = await fetch("/api/metadata");
  updateMeta(await response.json());
  emptyState();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) return;

  messageInput.value = "";
  sendButton.disabled = true;
  sendButton.textContent = "Running";

  const pending = {
    user: text,
    assistant_text: "Running model and tools...",
    rounds: [],
  };
  renderTurn(pending);

  try {
    const data = await postJson("/api/chat", { message: text });
    chat.lastElementChild?.remove();
    renderTurn(data.turn);
    updateMeta(data.metadata);
  } catch (error) {
    chat.lastElementChild?.remove();
    renderTurn({
      user: text,
      status: "provider_error",
      error: error.message,
      rounds: [],
    });
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Send";
    messageInput.focus();
  }
});

newTranscriptButton.addEventListener("click", async () => {
  newTranscriptButton.disabled = true;
  try {
    const data = await postJson("/api/new", {});
    updateMeta(data.metadata);
    chat.replaceChildren();
    emptyState();
  } finally {
    newTranscriptButton.disabled = false;
  }
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    form.requestSubmit();
  }
});

loadMetadata();
