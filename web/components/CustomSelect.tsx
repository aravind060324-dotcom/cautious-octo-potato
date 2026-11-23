"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";

type Option = { value: string; label: string };

type Props = {
  id: string;
  label: string;
  value: string;
  options: Option[];
  placeholder?: string;
  searchable?: boolean;
  required?: boolean;
  icon?: string;
  error?: string;
  onChange: (value: string) => void;
};

export function CustomSelect({
  id,
  label,
  value,
  options,
  placeholder = "Select",
  searchable = false,
  required = false,
  icon,
  error,
  onChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();

  const selected = options.find((option) => option.value === value);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return options;
    }
    return options.filter((option) =>
      option.label.toLowerCase().includes(needle),
    );
  }, [options, query]);

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div
        ref={rootRef}
        className={`control custom-select${open ? " is-open" : ""}${error ? " is-invalid" : ""}`}
      >
        {icon ? (
          <span className="material-symbols-outlined control-icon" aria-hidden>
            {icon}
          </span>
        ) : null}
        <button
          id={id}
          type="button"
          className="select-trigger"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((prev) => !prev)}
        >
          <span
            className={`select-label${!selected || !selected.value ? " is-placeholder" : ""}`}
          >
            {selected?.label || placeholder}
          </span>
          <span className="material-symbols-outlined chevron" aria-hidden>
            expand_more
          </span>
        </button>
        {open ? (
          <div className="select-menu">
            {searchable ? (
              <input
                className="select-search"
                type="search"
                value={query}
                placeholder="Search…"
                aria-label={`Search ${label}`}
                onChange={(event) => setQuery(event.target.value)}
                autoFocus
              />
            ) : null}
            <div className="select-options" role="listbox" id={listId}>
              {filtered.length === 0 ? (
                <div className="select-empty">No matches</div>
              ) : (
                filtered.map((option) => (
                  <button
                    key={`${option.value}-${option.label}`}
                    type="button"
                    role="option"
                    className={`select-option${option.value === value ? " is-selected" : ""}`}
                    aria-selected={option.value === value}
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                      setQuery("");
                    }}
                  >
                    {option.label}
                  </button>
                ))
              )}
            </div>
          </div>
        ) : null}
      </div>
      {required ? (
        <input
          tabIndex={-1}
          className="native-select"
          value={value}
          required
          onChange={() => undefined}
          aria-hidden
          style={{ position: "absolute", opacity: 0, pointerEvents: "none", height: 0, width: 0 }}
        />
      ) : null}
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}
