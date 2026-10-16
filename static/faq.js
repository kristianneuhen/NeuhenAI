(() => {
  const items = [...document.querySelectorAll(".faq-item")];

  items.forEach((item) => {
    const trigger = item.querySelector(".faq-trigger");

    trigger.addEventListener("click", () => {
      const shouldOpen = !item.classList.contains("is-open");

      items.forEach((otherItem) => {
        otherItem.classList.remove("is-open");
        otherItem.querySelector(".faq-trigger").setAttribute("aria-expanded", "false");
      });

      if (shouldOpen) {
        item.classList.add("is-open");
        trigger.setAttribute("aria-expanded", "true");
      }
    });
  });
})();
