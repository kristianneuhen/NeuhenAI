document.addEventListener("DOMContentLoaded", () => {
  const heading = document.querySelector(".hero-typewriter");
  if (!heading) return;

  const words = [...heading.querySelectorAll(".typewriter-word")];
  heading.classList.add("typewriter-ready");

  words.forEach((word, index) => {
    window.setTimeout(() => {
      word.classList.add("is-visible");
    }, 180 * index);
  });
});
