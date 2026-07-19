/* ============================================================
   UNKLE FUNK — WIP player + Q&A
   Self-hosted waveform playback (wavesurfer.js) + a Supabase-backed
   comment box per track, scoped to that track's question.

   ★ SETUP — fill these in once Supabase is ready, then commit ★
   ============================================================ */
const SUPABASE_URL = "";       // e.g. "https://xxxxx.supabase.co"
const SUPABASE_ANON_KEY = "";  // Project Settings → API → anon public key

(function () {
  "use strict";

  var supabaseReady = !!(SUPABASE_URL && SUPABASE_ANON_KEY);

  // ---------------------------------------------------------------
  // Waveform players
  // ---------------------------------------------------------------
  function initPlayers() {
    if (typeof WaveSurfer === "undefined") return;

    var players = [];
    document.querySelectorAll(".wip-player").forEach(function (el) {
      var src = el.dataset.audioSrc;
      if (!src) return;

      var waveEl = el.querySelector(".wip-waveform");
      var playBtn = el.querySelector(".wip-play");
      var timeEl = el.querySelector(".wip-time");

      el.classList.add("is-loading");

      var ws = WaveSurfer.create({
        container: waveEl,
        height: 52,
        waveColor: "rgba(154, 167, 180, 0.55)",
        progressColor: "#3BA7E0",
        cursorColor: "#AEDCF7",
        cursorWidth: 2,
        barWidth: 2,
        barGap: 2,
        barRadius: 2,
        normalize: true,
        url: src,
      });

      ws.on("ready", function () {
        el.classList.remove("is-loading");
        timeEl.textContent = fmtTime(ws.getDuration());
      });
      ws.on("error", function () {
        el.classList.remove("is-loading");
        el.classList.add("is-missing");
        timeEl.textContent = "";
        playBtn.disabled = true;
        var note = document.createElement("span");
        note.className = "wip-missing-note";
        note.textContent = "Audio coming soon";
        el.appendChild(note);
      });
      ws.on("audioprocess", function () {
        timeEl.textContent = fmtTime(ws.getCurrentTime());
      });
      ws.on("seeking", function () {
        timeEl.textContent = fmtTime(ws.getCurrentTime());
      });
      ws.on("play", function () {
        playBtn.dataset.playing = "true";
        // pause every other player — one WIP at a time
        players.forEach(function (other) {
          if (other !== ws && other.isPlaying()) other.pause();
        });
      });
      ws.on("pause", function () { playBtn.dataset.playing = "false"; });
      ws.on("finish", function () { playBtn.dataset.playing = "false"; });

      playBtn.addEventListener("click", function () { ws.playPause(); });
      players.push(ws);
    });
  }

  function fmtTime(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var m = Math.floor(sec / 60);
    var s = String(sec % 60).padStart(2, "0");
    return m + ":" + s;
  }

  // ---------------------------------------------------------------
  // Q&A — Supabase REST (no SDK needed, plain fetch)
  // ---------------------------------------------------------------
  function sbHeaders() {
    return {
      apikey: SUPABASE_ANON_KEY,
      Authorization: "Bearer " + SUPABASE_ANON_KEY,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    };
  }

  function loadFeedback(slug, listEl) {
    var url =
      SUPABASE_URL +
      "/rest/v1/wip_feedback?track_slug=eq." +
      encodeURIComponent(slug) +
      "&select=nickname,message,created_at&order=created_at.desc&limit=20";
    fetch(url, { headers: sbHeaders() })
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (rows) { renderFeedback(listEl, rows); })
      .catch(function () { renderFeedback(listEl, []); });
  }

  function renderFeedback(listEl, rows) {
    listEl.innerHTML = "";
    if (!rows || rows.length === 0) {
      var empty = document.createElement("li");
      empty.className = "wip-qa-item wip-qa-empty";
      empty.textContent = "No answers yet — be the first.";
      listEl.appendChild(empty);
      return;
    }
    rows.forEach(function (row) {
      var li = document.createElement("li");
      li.className = "wip-qa-item";
      var who = document.createElement("span");
      who.className = "who";
      who.textContent = (row.nickname || "Anonymous") + ":";
      var msg = document.createElement("span");
      msg.className = "msg";
      msg.textContent = row.message;
      li.appendChild(who);
      li.appendChild(msg);
      listEl.appendChild(li);
    });
  }

  function initQA() {
    document.querySelectorAll(".wip-qa").forEach(function (block) {
      var slug = block.dataset.track;
      var listEl = block.querySelector(".wip-qa-list");
      var form = block.querySelector(".wip-qa-form");
      var status = block.querySelector(".wip-qa-status");

      if (!supabaseReady) {
        block.querySelector(".wip-qa-form-wrap").innerHTML =
          '<p class="wip-qa-empty">Answers open once the site\u2019s comment box is wired up \u2014 check back soon.</p>';
        return;
      }

      loadFeedback(slug, listEl);

      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var honeypot = form.querySelector(".hp").value;
        if (honeypot) return; // bot caught

        var nickname = form.querySelector('[name="nickname"]').value.trim().slice(0, 40) || "Anonymous";
        var message = form.querySelector('[name="message"]').value.trim().slice(0, 500);
        if (!message) return;

        // light client-side rate limit: one post per track per 60s per browser
        var rlKey = "wip_rl_" + slug;
        var last = Number(localStorage.getItem(rlKey) || 0);
        if (Date.now() - last < 60000) {
          status.textContent = "One answer per track per minute \u2014 give it a moment.";
          status.dataset.state = "error";
          return;
        }

        status.textContent = "Posting\u2026";
        status.dataset.state = "";

        fetch(SUPABASE_URL + "/rest/v1/wip_feedback", {
          method: "POST",
          headers: sbHeaders(),
          body: JSON.stringify({ track_slug: slug, nickname: nickname, message: message }),
        })
          .then(function (r) {
            if (!r.ok) throw new Error("failed");
            return r.json();
          })
          .then(function () {
            localStorage.setItem(rlKey, String(Date.now()));
            form.reset();
            status.textContent = "Posted \u2014 thank you.";
            status.dataset.state = "";
            loadFeedback(slug, listEl);
          })
          .catch(function () {
            status.textContent = "Couldn\u2019t post that \u2014 try again in a moment.";
            status.dataset.state = "error";
          });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initPlayers();
      initQA();
    });
  } else {
    initPlayers();
    initQA();
  }
})();
