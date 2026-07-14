/* ============================================================
   UNKLE FUNK — unklefunk.music

   ★ THE ONLY NUMBER YOU EVER NEED TO TOUCH ★
   Bump TALLY when a track crosses the line. Commit. Done.
   ============================================================ */
const TALLY = 0;

(function () {
  "use strict";

  // ---- Tally badge -------------------------------------------------
  document.querySelectorAll("[data-tally]").forEach(function (el) {
    el.textContent = TALLY;
  });

  // ---- Click-to-load embeds (SoundCloud / YouTube facades) ---------
  document.querySelectorAll(".embed-facade").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var holder = document.createElement("div");
      holder.className = "embed-live";
      var iframe = document.createElement("iframe");
      iframe.src = btn.dataset.embed;
      iframe.title = btn.dataset.title || "Embedded player";
      iframe.loading = "lazy";
      iframe.setAttribute(
        "allow",
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      );
      iframe.setAttribute("allowfullscreen", "");
      holder.appendChild(iframe);
      btn.replaceWith(holder);
    });
  });

  // ---- Scroll reveal (the one piece of motion) ---------------------
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduced && "IntersectionObserver" in window) {
    document.documentElement.classList.add("reveal-ready");
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.1 }
    );
    document.querySelectorAll(".reveal").forEach(function (el) {
      io.observe(el);
    });
  }
})();
