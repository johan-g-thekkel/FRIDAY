(function () {
  "use strict";

  const $ = function (selector) { return document.querySelector(selector); };
  const state = {
    active: false,
    processing: false,
    stream: null,
    audioContext: null,
    analyser: null,
    recorder: null,
    chunks: [],
    speechActive: false,
    speechStartedAt: 0,
    lastVoiceAt: 0,
    frameId: 0,
    messages: [],
    voiceStatus: null,
    routes: []
  };

  function setStatus(message, kind) {
    $("#voice-status").textContent = message;
    const led = $("#voice-led");
    led.className = "state-dot" + (kind === "live" ? " live" : kind === "error" ? " error" : "");
  }

  function setPresence(mode, caption) {
    const face = $("#humanoid");
    face.classList.remove("listening", "thinking", "speaking");
    if (mode) face.classList.add(mode);
    $("#presence-caption").textContent = caption || "STANDBY · READY WHEN YOU ARE";
  }

  async function requestJson(path, options) {
    const response = await fetch(path, options || {});
    let body;
    const type = response.headers.get("content-type") || "";
    try { body = type.indexOf("application/json") >= 0 ? await response.json() : await response.text(); }
    catch (_) { body = null; }
    if (!response.ok) {
      const message = body && typeof body === "object" && body.detail
        ? body.detail
        : "Request failed (" + response.status + ")";
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function renderModelOptions(models, modelRoutes) {
    const select = $("#model-select");
    const localRoutes = (modelRoutes.routes || []).filter(function (route) {
      return route.id === "auto" || route.provider === "ollama-local";
    });
    state.routes = localRoutes;
    select.innerHTML = "";
    localRoutes.forEach(function (route) {
      const option = document.createElement("option");
      option.value = route.id;
      option.textContent = route.id === "auto" ? "Automatic (local-first)" : route.name;
      select.appendChild(option);
    });
    if (!localRoutes.some(function (route) { return route.id === "ollama"; }) && models && models.length) {
      const option = document.createElement("option");
      option.value = "ollama";
      option.textContent = "Ollama (configured default)";
      select.appendChild(option);
    }
    select.value = models && models.length ? "ollama" : "auto";
    $("#model-details").hidden = (models || []).length < 2;
  }

  async function refreshStatus() {
    try {
      const health = await requestJson("/health");
      $("#backend-led").className = "status-led good";
      $("#backend-status").textContent = health.status === "ok" ? "FRIDAY backend connected" : "Backend responded";
    } catch (error) {
      $("#backend-led").className = "status-led bad";
      $("#backend-status").textContent = "Backend disconnected";
      $("#model-status").textContent = "API is not reachable";
      $("#speech-status").textContent = "Check server terminal";
      setStatus("Could not reach /health. Open the forwarded port for the FRIDAY backend.", "error");
      return;
    }

    try {
      const voice = await requestJson("/api/v1/voice/status");
      state.voiceStatus = voice;
      const models = voice.models || [];
      if (models.length) {
        $("#model-status").textContent = "Ollama · " + (voice.default_model || models[0]);
      } else {
        $("#model-status").textContent = "Ollama not ready";
      }
      $("#speech-status").textContent = voice.transcription_ready ? "Local Whisper ready" : "Whisper setup required";
      $("#speech-status").title = voice.transcription_note || "";
      const routes = await requestJson("/api/v1/models");
      renderModelOptions(models, routes);
      if (!models.length) {
        setStatus("Backend connected. No local Ollama model detected in this runtime.", "error");
        $("#voice-help").textContent = "Start Ollama in the same runtime as FRIDAY and pull a model: ollama pull qwen2.5:3b. In Codespaces, that model runs in the Codespace, not on your laptop.";
      } else if (!voice.transcription_ready) {
        setStatus("Local model detected. Install offline Whisper to enable local microphone transcription.", "error");
        $("#voice-help").textContent = "Install local speech recognition in the terminal with: pip install -r requirements-voice.txt. The first transcription downloads the Whisper model once.";
      } else {
        setStatus("Ready. Tap Activate FRIDAY and speak after the microphone permission prompt.", "");
        $("#voice-help").textContent = "Audio is transcribed by local Whisper. Pause after each request; FRIDAY answers out loud, then listens again.";
      }
    } catch (error) {
      setStatus("Backend is up, but voice readiness could not be checked: " + error.message, "error");
    }
  }

  function chooseMimeType() {
    if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return "";
    const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];
    for (let i = 0; i < candidates.length; i++) {
      if (MediaRecorder.isTypeSupported(candidates[i])) return candidates[i];
    }
    return "";
  }

  function startRecorder() {
    if (!state.active || state.processing || !state.stream) return;
    const mime = chooseMimeType();
    try {
      state.chunks = [];
      state.recorder = new MediaRecorder(state.stream, mime ? { mimeType: mime } : undefined);
      state.recorder.ondataavailable = function (event) {
        if (!event.data || !event.data.size) return;
        state.chunks.push(event.data);
        // Keep only a short pre-roll while idle. When speech starts, preserve the whole utterance.
        if (!state.speechActive) state.chunks = state.chunks.slice(-8);
      };
      state.recorder.onerror = function () {
        setStatus("Microphone recorder failed. Try another browser or check microphone access.", "error");
      };
      state.recorder.onstop = async function () {
        const type = state.recorder && state.recorder.mimeType ? state.recorder.mimeType : "audio/webm";
        const blob = new Blob(state.chunks, { type: type });
        state.chunks = [];
        state.speechActive = false;
        if (!state.active) return;
        if (blob.size > 1500) await processUtterance(blob);
        if (state.active) startRecorder();
      };
      state.recorder.start(250);
    } catch (error) {
      setStatus("Could not start local audio capture: " + error.message, "error");
      stopListening();
    }
  }

  function watchMicrophone() {
    if (!state.active || !state.analyser) return;
    const samples = new Float32Array(state.analyser.fftSize);
    state.analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    const rms = Math.sqrt(sum / samples.length);
    const now = Date.now();

    if (rms > 0.018 && !state.processing) {
      if (!state.speechActive) {
        state.speechActive = true;
        state.speechStartedAt = now;
        setStatus("Hearing you… keep speaking, then pause.", "live");
        setPresence("listening", "LISTENING · LOCAL AUDIO CAPTURE");
        $("#activate-label").textContent = "Listening…";
      }
      state.lastVoiceAt = now;
    } else if (
      state.speechActive &&
      now - state.lastVoiceAt > 1050 &&
      now - state.speechStartedAt > 450 &&
      state.recorder &&
      state.recorder.state === "recording"
    ) {
      setStatus("Transcribing on-device…", "live");
      setPresence("thinking", "PROCESSING · LOCAL WHISPER");
      // Keep speechActive true until the final MediaRecorder dataavailable event arrives.
      state.recorder.stop();
    }
    state.frameId = requestAnimationFrame(watchMicrophone);
  }

  async function processUtterance(blob) {
    state.processing = true;
    try {
      const form = new FormData();
      const ext = blob.type.indexOf("ogg") >= 0 ? "ogg" : blob.type.indexOf("mp4") >= 0 ? "m4a" : "webm";
      form.append("audio", blob, "friday-utterance." + ext);
      const transcribed = await requestJson("/api/v1/voice/transcribe", { method: "POST", body: form });
      const text = String(transcribed.text || "").trim();
      if (!text) return;

      $("#transcript").textContent = text;
      $("#transcript").classList.remove("muted");
      state.messages.push({ role: "user", content: text });
      state.messages = state.messages.slice(-20);
      $("#turn-count").textContent = state.messages.filter(function (message) { return message.role === "user"; }).length + " SPOKEN TURN(S)";
      $("#response").textContent = "Thinking with the selected model…";
      $("#response").classList.remove("muted");
      $("#response-source").textContent = "MODEL WORKING";
      setStatus("Thinking with " + ($("#model-status").textContent || "the selected model") + "…", "live");
      setPresence("thinking", "REASONING · LOCAL-FIRST ROUTING");

      const route = $("#model-select").value || "auto";
      const answer = await requestJson("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ messages: state.messages, model_route: route })
      });
      state.messages.push({ role: "assistant", content: answer.answer });
      state.messages = state.messages.slice(-20);
      $("#response").textContent = answer.answer;
      $("#response-source").textContent = (answer.provider || "model") + (answer.model ? " · " + answer.model : "");
      setPresence("speaking", "RESPONDING · VOICE OUTPUT");
      setStatus("Answer ready. Speaking now…", "live");
      await speak(answer.answer);
    } catch (error) {
      $("#response").textContent = error.message || "The request failed.";
      $("#response").classList.remove("muted");
      $("#response-source").textContent = error.status === 503 ? "LOCAL COMPONENT MISSING" : "REQUEST FAILED";
      if (error.status === 503 && /Whisper|transcription|speech recognition/i.test(error.message)) {
        $("#speech-status").textContent = "Install requirements-voice.txt";
      }
      setPresence("", "ATTENTION · SETUP REQUIRED");
      setStatus(error.message || "The voice request failed.", "error");
      if (error.status === 503 && /Ollama|model/i.test(error.message)) {
        $("#model-status").textContent = "No matching model installed";
      }
    } finally {
      state.processing = false;
      if (state.active && (!window.speechSynthesis || !window.speechSynthesis.speaking)) {
        setPresence("listening", "LISTENING · LOCAL AUDIO CAPTURE");
        setStatus("Listening again. Speak when ready.", "live");
      }
    }
  }

  function speak(text) {
    return new Promise(function (resolve) {
      if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
        setStatus("Speech synthesis is unavailable in this browser.", "error");
        resolve();
        return;
      }
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 0.94;
      utterance.volume = 1;
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(function (voice) { return /^en-IN/i.test(voice.lang); }) ||
        voices.find(function (voice) { return /^en-GB/i.test(voice.lang); }) ||
        voices.find(function (voice) { return /^en/i.test(voice.lang); });
      if (preferred) utterance.voice = preferred;
      utterance.lang = preferred ? preferred.lang : "en-IN";
      utterance.onstart = function () { setPresence("speaking", "SPEAKING · LOCAL SYSTEM VOICE"); };
      utterance.onend = function () { resolve(); };
      utterance.onerror = function () { resolve(); };
      window.speechSynthesis.speak(utterance);
    });
  }

  async function startListening() {
    if (state.active) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      setStatus("This browser does not support microphone recording. Try the latest Chrome or Edge.", "error");
      return;
    }
    if (!state.voiceStatus || !state.voiceStatus.transcription_ready) {
      setStatus("Offline Whisper is not installed. Run pip install -r requirements-voice.txt in the backend terminal.", "error");
      $("#response").textContent = "Voice input is designed to use local Whisper. Install requirements-voice.txt, restart FRIDAY, and try again.";
      $("#response").classList.remove("muted");
      $("#response-source").textContent = "LOCAL SPEECH SETUP REQUIRED";
      return;
    }
    try {
      state.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("Web Audio is unsupported in this browser.");
      state.audioContext = new AudioContextClass();
      await state.audioContext.resume();
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 2048;
      const source = state.audioContext.createMediaStreamSource(state.stream);
      source.connect(state.analyser);
      state.active = true;
      state.speechActive = false;
      $("#activate-button").hidden = true;
      $("#stop-button").hidden = false;
      $("#activate-label").textContent = "Listening…";
      setPresence("listening", "LISTENING · LOCAL AUDIO CAPTURE");
      setStatus("Microphone is active. Speak naturally, then pause.", "live");
      startRecorder();
      watchMicrophone();
    } catch (error) {
      setStatus("Microphone permission or audio setup failed: " + error.message, "error");
      stopListening();
    }
  }

  function stopListening() {
    state.active = false;
    state.speechActive = false;
    if (state.frameId) cancelAnimationFrame(state.frameId);
    if (state.recorder && state.recorder.state !== "inactive") {
      try { state.recorder.stop(); } catch (_) {}
    }
    if (state.stream) state.stream.getTracks().forEach(function (track) { track.stop(); });
    state.stream = null;
    if (state.audioContext && state.audioContext.state !== "closed") state.audioContext.close().catch(function () {});
    state.audioContext = null;
    state.analyser = null;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    $("#activate-button").hidden = false;
    $("#stop-button").hidden = true;
    $("#activate-label").textContent = "Activate FRIDAY";
    setPresence("", "STANDBY · VOICE SESSION PAUSED");
    setStatus("Voice session ended");
  }

  $("#activate-button").addEventListener("click", startListening);
  $("#stop-button").addEventListener("click", stopListening);
  $("#model-select").addEventListener("change", function () {
    const route = state.routes.find(function (item) { return item.id === $("#model-select").value; });
    $("#model-status").textContent = route && route.model ? "Ollama · " + route.model : route && route.id === "auto" ? "Automatic local-first routing" : "Ollama model selected";
  });
  window.addEventListener("beforeunload", stopListening);

  refreshStatus();
  window.setInterval(function () {
    if (!state.active) refreshStatus();
  }, 15000);
})();
