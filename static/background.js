(() => {
  "use strict";

  const canvas = document.getElementById("ambient-background");
  if (!canvas) return;

  const context = canvas.getContext("2d");
  if (!context) return;

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  // These are the values used by the supplied DotDistortionShader demo.
  const dotGap = 14;
  const dotSize = 1;
  const mouseRadius = 100;
  const distortionStrength = 1.2;
  const returnSpeed = 0.06;
  const mouse = { x: -1000, y: -1000, previousX: -1000, previousY: -1000 };
  let dots = [];
  let animationFrame = 0;
  let isVisible = !document.hidden;

  function createDots(width, height) {
    const createdDots = [];
    const columns = Math.ceil(width / dotGap) + 2;
    const rows = Math.ceil(height / dotGap) + 2;
    const offsetX = (width % dotGap) / 2;
    const offsetY = (height % dotGap) / 2;

    for (let column = 0; column < columns; column += 1) {
      for (let row = 0; row < rows; row += 1) {
        const x = column * dotGap + offsetX;
        const y = row * dotGap + offsetY;
        const noise =
          Math.sin(column * 0.3 + row * 0.2) * 0.3 +
          Math.sin(column * 0.7 - row * 0.5) * 0.2 +
          Math.sin((column + row) * 0.4) * 0.2 +
          Math.random() * 0.3;

        createdDots.push({
          baseX: x,
          baseY: y,
          x,
          y,
          brightness: Math.max(0.1, Math.min(1, 0.3 + noise)),
          phase: Math.random() * Math.PI * 2,
        });
      }
    }

    return createdDots;
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = window.innerWidth;
    const height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    dots = createDots(width, height);
  }

  function resetDots() {
    for (const dot of dots) {
      dot.x = dot.baseX;
      dot.y = dot.baseY;
    }
  }

  function draw(timestamp) {
    if (!isVisible) return;

    const width = window.innerWidth;
    const height = window.innerHeight;
    context.clearRect(0, 0, width, height);
    const time = timestamp * 0.001;

    for (const dot of dots) {
      const dx = mouse.x - dot.baseX;
      const dy = mouse.y - dot.baseY;
      const distance = Math.hypot(dx, dy);
      const activeMouse = !prefersReducedMotion.matches && distance < mouseRadius;
      const falloff = activeMouse ? (1 - distance / mouseRadius) ** 2 : 0;
      const mouseDeltaX = mouse.x - mouse.previousX;
      const mouseDeltaY = mouse.y - mouse.previousY;

      const targetX = dot.baseX + mouseDeltaX * falloff * distortionStrength * 0.3;
      const targetY = dot.baseY + mouseDeltaY * falloff * distortionStrength * 0.3;
      dot.x += (targetX - dot.x) * returnSpeed;
      dot.y += (targetY - dot.y) * returnSpeed;

      const breathing = prefersReducedMotion.matches
        ? 0
        : Math.sin(time * 0.8 + dot.phase) * 0.12;
      const brightness = Math.max(0.05, Math.min(1, dot.brightness + breathing + falloff * 0.35));

      context.globalAlpha = brightness;
      context.fillStyle = "#0284c7";
      context.shadowColor = "#0284c7";
      context.shadowBlur = falloff > 0.04 ? 8 + falloff * 16 : 0;
      context.beginPath();
      context.arc(dot.x, dot.y, dotSize, 0, Math.PI * 2);
      context.fill();
    }

    context.globalAlpha = 1;
    context.shadowBlur = 0;
    mouse.previousX += (mouse.x - mouse.previousX) * 0.1;
    mouse.previousY += (mouse.y - mouse.previousY) * 0.1;
    animationFrame = window.requestAnimationFrame(draw);
  }

  function updateMouse(event) {
    mouse.x = event.clientX;
    mouse.y = event.clientY;
    if (mouse.previousX < 0) {
      mouse.previousX = mouse.x;
      mouse.previousY = mouse.y;
    }
  }

  function handleVisibility() {
    isVisible = !document.hidden;
    if (isVisible) {
      resetDots();
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(draw);
    }
  }

  window.addEventListener("resize", resize, { passive: true });
  window.addEventListener("pointermove", updateMouse, { passive: true });
  document.addEventListener("visibilitychange", handleVisibility);
  resize();
  animationFrame = window.requestAnimationFrame(draw);
})();
