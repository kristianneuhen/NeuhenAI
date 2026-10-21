(() => {
  "use strict";

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  document.querySelectorAll(".glow-card").forEach((card) => {
    function placeGlow(event) {
      const bounds = card.getBoundingClientRect();
      card.style.setProperty("--glow-x", `${event.clientX - bounds.left}px`);
      card.style.setProperty("--glow-y", `${event.clientY - bounds.top}px`);
    }

    card.addEventListener("pointerenter", (event) => {
      placeGlow(event);
      card.classList.add("is-glowing");
    });
    card.addEventListener("pointermove", placeGlow);
    card.addEventListener("pointerleave", () => card.classList.remove("is-glowing"));
  });
})();
