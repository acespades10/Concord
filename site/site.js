const copyButton = document.querySelector("[data-copy]");
const navigation = document.querySelector("header.nav");
const menuButton = navigation?.querySelector(".nav__toggle");
const syncMenu = () => {
  const open = navigation.classList.contains("is-open");
  menuButton.textContent = open ? "Close" : "Menu";
  menuButton.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  document.querySelector("main").inert = open;
  document.querySelector("footer").inert = open;
};
if (navigation && menuButton) {
  new MutationObserver(syncMenu).observe(navigation, {
    attributes: true,
    attributeFilter: ["class"],
  });
  syncMenu();
}
copyButton?.addEventListener("click", async () => {
  const source = document.getElementById(copyButton.dataset.copy);
  const status = document.querySelector(".copy-status");
  try {
    await navigator.clipboard.writeText(source.innerText);
    status.textContent = "Commands copied.";
  } catch {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(source);
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent =
      "Copy is unavailable here. Commands selected; use your browser’s copy command.";
  }
});
