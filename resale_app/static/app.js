// Small progressive enhancements. Every page works without this file.
(function () {
  // Copy buttons: <button data-copy="#element-id">
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-copy]");
    if (!btn) return;
    var target = document.querySelector(btn.getAttribute("data-copy"));
    if (!target) return;
    var text = target.innerText.replace(/\s+$/, "");
    var done = function () {
      var old = btn.textContent;
      btn.textContent = "Copied";
      btn.classList.add("done");
      setTimeout(function () { btn.textContent = old; btn.classList.remove("done"); }, 1400);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else {
      fallbackCopy(text);
      done();
    }
  });
  function fallbackCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* nothing more to try */ }
    document.body.removeChild(ta);
  }

  // Character counters: <input data-counter="80">
  document.querySelectorAll("[data-counter]").forEach(function (field) {
    var max = parseInt(field.getAttribute("data-counter"), 10);
    var out = document.createElement("span");
    out.className = "counter";
    field.parentNode.insertBefore(out, field.nextSibling);
    function update() {
      out.textContent = field.value.length + " / " + max;
      out.classList.toggle("over", field.value.length > max);
    }
    field.addEventListener("input", update);
    update();
  });

  // Upload page: show how many photos were picked.
  var files = document.getElementById("files");
  var count = document.getElementById("file-count");
  if (files && count) {
    files.addEventListener("change", function () {
      var n = files.files.length;
      count.textContent = n ? n + " photo" + (n === 1 ? "" : "s") + " selected" : "";
    });
  }

  // Confirm destructive forms: <form data-confirm="Really?">
  document.addEventListener("submit", function (ev) {
    var msg = ev.target.getAttribute && ev.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) ev.preventDefault();
  });

  // Make the label-buttons keyboard friendly.
  document.addEventListener("keydown", function (ev) {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches && ev.target.matches("label.btn[for]")) {
      ev.preventDefault();
      ev.target.click();
    }
  });

  // Pages that are waiting on the analysis worker: <body data-autorefresh="6">.
  // Skip the reload while someone is typing or has an edit form open, so nothing is lost.
  var every = parseInt(document.body.getAttribute("data-autorefresh") || "0", 10);
  if (every > 0) {
    setInterval(function () {
      var a = document.activeElement;
      var typing = a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.tagName === "SELECT");
      var editing = document.querySelector(".edit-toggle:checked, details[open] textarea:focus");
      if (!typing && !editing && !document.hidden) window.location.reload();
    }, every * 1000);
  }
})();
