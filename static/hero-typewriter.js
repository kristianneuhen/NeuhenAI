document.addEventListener("DOMContentLoaded", () => {
  const heading = document.querySelector(".hero-typewriter");
  if (!heading) return;

  const words = [...heading.querySelectorAll(".typewriter-word")];
  heading.classList.add("typewriter-ready");

  let characterIndex = 0;

  words.forEach((word) => {
    const text = word.textContent.trim();
    word.textContent = "";

    [...text].forEach((character) => {
      const characterNode = document.createElement("span");
      characterNode.className = "typewriter-char";
      characterNode.textContent = character;
      word.appendChild(characterNode);

      window.setTimeout(() => {
        characterNode.classList.add("is-visible");
      }, 45 * characterIndex);
      characterIndex += 1;
    });

    characterIndex += 2;
  });
});
