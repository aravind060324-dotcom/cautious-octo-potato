"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  id: string;
  value: string;
  suggestions: string[];
  error?: string;
  onChange: (value: string) => void;
};

export function CuisineSuggest({
  id,
  value,
  suggestions,
  error,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const matches = useMemo(() => {
    const needle = value.trim().toLowerCase();
    return suggestions
      .filter((name) => !needle || name.toLowerCase().includes(needle))
      .slice(0, 8);
  }, [suggestions, value]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div className="field">
      <label htmlFor={id}>Cuisine</label>
      <div
        ref={rootRef}
        className={`control suggest-field${open && matches.length ? " is-open" : ""}${error ? " is-invalid" : ""}`}
      >
        <span className="material-symbols-outlined control-icon" aria-hidden>
          restaurant
        </span>
        <input
          id={id}
          value={value}
          autoComplete="off"
          placeholder="Italian, North Indian…"
          role="combobox"
          aria-expanded={open && matches.length > 0}
          aria-autocomplete="list"
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
        />
        {open && matches.length > 0 ? (
          <div className="select-menu suggest-menu" role="listbox">
            {matches.map((name) => (
              <button
                key={name}
                type="button"
                role="option"
                className="select-option"
                onMouseDown={(event) => {
                  event.preventDefault();
                  onChange(name);
                  setOpen(false);
                }}
              >
                {name}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}
