import { searchForView, VIEWS, type ViewId } from "../views/views";

/**
 * Switches between the views. Each tab is a link to the same page with its ``view`` parameter set,
 * so the view can be shared; the click is handled in place, with no client router.
 */
export function ViewTabs({
  active,
  onSelect,
}: {
  active: ViewId;
  onSelect: (view: ViewId) => void;
}) {
  return (
    <nav aria-label="Views" className="border-b border-rule">
      <ul className="flex gap-1">
        {VIEWS.map((view) => {
          const isActive = view.id === active;
          const href = `${window.location.pathname}${searchForView(window.location.search, view.id)}`;
          return (
            <li key={view.id}>
              <a
                href={href}
                aria-current={isActive ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  onSelect(view.id);
                }}
                className={`-mb-px inline-block border-b-2 px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forecast ${
                  isActive
                    ? "border-forecast text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {view.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
