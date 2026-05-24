document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const message = form.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

const SWIPE_REVEAL_WIDTH = 108;
const SWIPE_OPEN_THRESHOLD = 54;
const SWIPE_INTENT_THRESHOLD = 10;

let activeSwipe = null;

function getSwipeSurface(card) {
  return card.querySelector("[data-swipe-surface]");
}

function getSwipeActions(card) {
  return card.querySelector(".product-card-swipe-actions");
}

function setSwipeActionAvailability(card, isAvailable) {
  const actions = getSwipeActions(card);
  if (!actions) {
    return;
  }

  actions.setAttribute("aria-hidden", String(!isAvailable));
  actions.querySelectorAll("button, a, input, select, textarea").forEach((element) => {
    element.tabIndex = isAvailable ? 0 : -1;
  });
}

function setCardOffset(card, offset) {
  const surface = getSwipeSurface(card);
  if (!surface) {
    return;
  }

  surface.style.transform = offset > 0 ? `translateX(${-offset}px)` : "";
}

function openSwipeCard(card) {
  card.classList.add("is-swipe-open");
  setCardOffset(card, SWIPE_REVEAL_WIDTH);
  setSwipeActionAvailability(card, true);
}

function closeSwipeCard(card) {
  card.classList.remove("is-swipe-open", "is-dragging");
  setCardOffset(card, 0);
  setSwipeActionAvailability(card, false);
}

function closeOpenSwipeCards(exceptCard = null) {
  document.querySelectorAll("[data-swipe-card].is-swipe-open").forEach((card) => {
    if (card !== exceptCard) {
      closeSwipeCard(card);
    }
  });
}

function shouldIgnoreSwipeStart(target) {
  return Boolean(target.closest(".product-card-swipe-actions"));
}

document.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) {
    return;
  }

  const surface = event.target.closest("[data-swipe-surface]");
  if (!surface || shouldIgnoreSwipeStart(event.target)) {
    return;
  }

  const card = surface.closest("[data-swipe-card]");
  if (!card) {
    return;
  }

  closeOpenSwipeCards(card);
  activeSwipe = {
    card,
    surface,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startOffset: card.classList.contains("is-swipe-open") ? SWIPE_REVEAL_WIDTH : 0,
    currentOffset: card.classList.contains("is-swipe-open") ? SWIPE_REVEAL_WIDTH : 0,
    hasHorizontalIntent: false,
    didSwipe: false,
  };

  surface.setPointerCapture(event.pointerId);
});

document.addEventListener("pointermove", (event) => {
  if (!activeSwipe || activeSwipe.pointerId !== event.pointerId) {
    return;
  }

  const deltaX = event.clientX - activeSwipe.startX;
  const deltaY = event.clientY - activeSwipe.startY;
  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);

  if (!activeSwipe.hasHorizontalIntent) {
    if (absX < SWIPE_INTENT_THRESHOLD && absY < SWIPE_INTENT_THRESHOLD) {
      return;
    }

    if (absY > absX) {
      activeSwipe = null;
      return;
    }

    activeSwipe.hasHorizontalIntent = true;
    activeSwipe.card.classList.add("is-dragging");
  }

  event.preventDefault();
  const nextOffset = Math.min(
    SWIPE_REVEAL_WIDTH,
    Math.max(0, activeSwipe.startOffset - deltaX)
  );
  activeSwipe.currentOffset = nextOffset;
  activeSwipe.didSwipe = activeSwipe.didSwipe || Math.abs(nextOffset - activeSwipe.startOffset) > 8;
  setCardOffset(activeSwipe.card, nextOffset);
});

function finishSwipe(event) {
  if (!activeSwipe || activeSwipe.pointerId !== event.pointerId) {
    return;
  }

  const swipe = activeSwipe;
  activeSwipe = null;
  swipe.card.classList.remove("is-dragging");

  if (!swipe.hasHorizontalIntent) {
    return;
  }

  if (swipe.didSwipe) {
    swipe.card.dataset.suppressNextClick = "true";
  }

  if (swipe.currentOffset >= SWIPE_OPEN_THRESHOLD) {
    openSwipeCard(swipe.card);
  } else {
    closeSwipeCard(swipe.card);
  }
}

document.addEventListener("pointerup", finishSwipe);
document.addEventListener("pointercancel", finishSwipe);

document.addEventListener(
  "click",
  (event) => {
    const card = event.target.closest("[data-swipe-card]");
    if (card?.dataset.suppressNextClick === "true") {
      event.preventDefault();
      event.stopPropagation();
      delete card.dataset.suppressNextClick;
      return;
    }

    if (!card) {
      closeOpenSwipeCards();
    }
  },
  true
);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeOpenSwipeCards();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-swipe-card]").forEach((card) => {
    setSwipeActionAvailability(card, card.classList.contains("is-swipe-open"));
  });
});
