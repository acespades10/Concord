const copyButton = document.querySelector("[data-copy]");
const navigation = document.querySelector("header.nav");
const menuButton = navigation?.querySelector(".nav__toggle");
const root = document.documentElement;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
document.addEventListener(
  "pointerdown",
  () => {
    root.dataset.input = "pointer";
  },
  true,
);
document.addEventListener(
  "keydown",
  () => {
    root.dataset.input = "keyboard";
    document.getAnimations().forEach((animation) => animation.cancel());
  },
  true,
);

const syncMenu = () => {
  const open = navigation.classList.contains("is-open");
  menuButton.textContent = open ? "Close" : "Menu";
  menuButton.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  document.querySelector("main").inert = open;
  document.querySelector("footer").inert = open;
  if (open)
    navigation.querySelector(".nav__link")?.focus({ preventScroll: true });
};
if (navigation && menuButton) {
  new MutationObserver(syncMenu).observe(navigation, {
    attributes: true,
    attributeFilter: ["class"],
  });
  syncMenu();
}
navigation?.addEventListener("keydown", (event) => {
  if (event.key !== "Tab" || !navigation.classList.contains("is-open")) return;
  const controls = [
    ...navigation.querySelectorAll("a[href]:not(.skip-link), button"),
  ].filter(
    (element) =>
      element.getClientRects().length &&
      getComputedStyle(element).visibility !== "hidden",
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});

const stagePanels = document.querySelector(".stage-panels");
if (stagePanels) {
  // The shared kit selects tabs; keep its fades aligned with this page's input mode.
  new MutationObserver((records) => {
    const tokens = getComputedStyle(root);
    for (const panel of new Set(records.map((record) => record.target))) {
      const animations = panel.getAnimations();
      if (
        panel.hidden ||
        root.dataset.input === "keyboard" ||
        reducedMotion.matches
      ) {
        animations.forEach((animation) => animation.cancel());
      } else {
        animations.slice(0, -1).forEach((animation) => animation.cancel());
        animations.at(-1)?.effect.updateTiming({
          duration: parseFloat(tokens.getPropertyValue("--m-in")),
          easing: tokens.getPropertyValue("--m-ease").trim(),
        });
      }
    }
  }).observe(stagePanels, {
    subtree: true,
    attributes: true,
    attributeFilter: ["hidden"],
  });
}
document
  .querySelector('[role="tablist"]')
  ?.addEventListener("keydown", (event) => {
    if (!["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const tabs = [...event.currentTarget.querySelectorAll('[role="tab"]')];
    const target = event.key === "Home" ? tabs[0] : tabs.at(-1);
    target.click();
    target.focus();
  });

copyButton?.addEventListener("click", async () => {
  const source = document.getElementById(copyButton.dataset.copy);
  const status = document.querySelector(".copy-status");
  const label = copyButton.querySelector("[data-copy-label]");
  status.textContent = "";
  try {
    await navigator.clipboard.writeText(source.innerText);
    copyButton.dataset.copied = "true";
    label.textContent = "Copied";
    copyButton.setAttribute("aria-label", "Copy commands again");
    status.textContent = "Commands copied.";
  } catch {
    delete copyButton.dataset.copied;
    label.textContent = "Copy commands";
    copyButton.removeAttribute("aria-label");
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(source);
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent =
      "Copy is unavailable here. Commands selected; use your browser’s copy command.";
  }
});
