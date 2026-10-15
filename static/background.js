(() => {
  "use strict";

  const canvas = document.getElementById("ambient-background");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  if (!context) return;

  const dotGap = 14;
  const dotSize = 1;

  function drawBackground() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = window.innerWidth;
    const height = window.innerHeight;
    const columns = Math.ceil(width / dotGap) + 2;
    const rows = Math.ceil(height / dotGap) + 2;
    const offsetX = (width % dotGap) / 2;
    const offsetY = (height % dotGap) / 2;

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#0284c7";

    for (let column = 0; column < columns; column += 1) {
      for (let row = 0; row < rows; row += 1) {
        const brightness = 0.22 + Math.max(
          0,
          Math.sin(column * 0.3 + row * 0.2) * 0.14 +
          Math.sin(column * 0.7 - row * 0.5) * 0.1
        );

        context.globalAlpha = brightness;
        context.beginPath();
        context.arc(
          column * dotGap + offsetX,
          row * dotGap + offsetY,
          dotSize,
          0,
          Math.PI * 2
        );
        context.fill();
      }
    }

    context.globalAlpha = 1;
  }

  window.addEventListener("resize", drawBackground, { passive: true });
  drawBackground();
})();
