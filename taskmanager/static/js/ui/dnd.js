// HTML5 drag & drop helpers: sortable lists (with cross-list moves) and simple drop zones.

/**
 * sortable(root, { item: ".task-row", list: ".task-list", onDrop({ id, list, ids, fromList }) })
 * Items need data-id and draggable="true". Lists may carry data-status / data-date.
 */
export function sortable(root, { item, list, onDrop, horizontal = false }) {
  let dragEl = null, fromList = null;

  root.addEventListener("dragstart", (e) => {
    const it = e.target.closest?.(item);
    if (!it || !root.contains(it)) return;
    dragEl = it; fromList = it.closest(list);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", it.dataset.id);
    requestAnimationFrame(() => it.classList.add("dragging"));
    root.classList.add("is-dragging");
  });

  root.addEventListener("dragover", (e) => {
    if (!dragEl) return;
    const l = e.target.closest?.(list);
    if (!l || !root.contains(l)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    root.querySelectorAll(".drop-target").forEach((x) => x !== l && x.classList.remove("drop-target"));
    l.classList.add("drop-target");
    const after = closestAfter(l, item, horizontal ? e.clientX : e.clientY, horizontal);
    if (after == null) { if (l.lastElementChild !== dragEl) l.appendChild(dragEl); }
    else if (after !== dragEl && after.previousElementSibling !== dragEl) l.insertBefore(dragEl, after);
  });

  root.addEventListener("drop", (e) => {
    if (!dragEl) return;
    const l = dragEl.closest(list);
    if (!l) return;
    e.preventDefault();
    const ids = [...l.querySelectorAll(item)].map((x) => Number(x.dataset.id));
    onDrop?.({ id: Number(dragEl.dataset.id), list: l, ids, fromList });
  });

  root.addEventListener("dragend", () => {
    dragEl?.classList.remove("dragging");
    root.classList.remove("is-dragging");
    root.querySelectorAll(".drop-target").forEach((x) => x.classList.remove("drop-target"));
    dragEl = null; fromList = null;
  });
}

function closestAfter(container, sel, pos, horizontal) {
  const els = [...container.querySelectorAll(`${sel}:not(.dragging)`)];
  let best = null, bestOff = -Infinity;
  for (const el of els) {
    const r = el.getBoundingClientRect();
    const off = pos - (horizontal ? r.left + r.width / 2 : r.top + r.height / 2);
    if (off < 0 && off > bestOff) { bestOff = off; best = el; }
  }
  return best;
}

/** dropZones(root, { item: ".cal-chip", zone: ".cal-day", onDrop({ id, zone }) }) */
export function dropZones(root, { item, zone, onDrop }) {
  let id = null;
  root.addEventListener("dragstart", (e) => {
    const it = e.target.closest?.(item);
    if (!it) return;
    id = Number(it.dataset.id);
    e.dataTransfer.setData("text/plain", String(id));
    e.dataTransfer.effectAllowed = "move";
    requestAnimationFrame(() => it.classList.add("dragging"));
  });
  root.addEventListener("dragover", (e) => {
    const z = e.target.closest?.(zone);
    if (!z || id == null) return;
    e.preventDefault();
    root.querySelectorAll(".drop-target").forEach((x) => x !== z && x.classList.remove("drop-target"));
    z.classList.add("drop-target");
  });
  root.addEventListener("dragleave", (e) => {
    const z = e.target.closest?.(zone);
    if (z && !z.contains(e.relatedTarget)) z.classList.remove("drop-target");
  });
  root.addEventListener("drop", (e) => {
    const z = e.target.closest?.(zone);
    if (!z || id == null) return;
    e.preventDefault();
    z.classList.remove("drop-target");
    onDrop?.({ id, zone: z });
  });
  root.addEventListener("dragend", () => {
    root.querySelectorAll(".dragging").forEach((x) => x.classList.remove("dragging"));
    root.querySelectorAll(".drop-target").forEach((x) => x.classList.remove("drop-target"));
    id = null;
  });
}
