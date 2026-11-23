"use client";

type Props = {
  active: boolean;
  onClick: () => void;
  label?: string;
};

export function FavoritesButton({ active, onClick, label = "Favorite" }: Props) {
  return (
    <button
      type="button"
      className={`icon-btn${active ? " is-active" : ""}`}
      aria-pressed={active}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
    >
      <span
        className={`material-symbols-outlined${active ? " filled" : ""}`}
        aria-hidden
      >
        favorite
      </span>
      {label}
    </button>
  );
}
