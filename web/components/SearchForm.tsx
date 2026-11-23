"use client";

import type { Budget, SearchPreferences } from "@/lib/types";
import { CuisineSuggest } from "./CuisineSuggest";
import { CustomSelect } from "./CustomSelect";

type Props = {
  value: SearchPreferences;
  locations: string[];
  cuisines: string[];
  loading: boolean;
  errors: Partial<Record<keyof SearchPreferences | "form", string>>;
  onChange: (next: SearchPreferences) => void;
  onSubmit: () => void;
};

const BUDGETS: { value: Budget | ""; label: string; hint: string }[] = [
  { value: "", label: "Any", hint: "No filter" },
  { value: "low", label: "Low", hint: "≤ ₹500" },
  { value: "medium", label: "Medium", hint: "₹501–₹1,000" },
  { value: "high", label: "High", hint: "₹1,001+" },
];

export function SearchForm({
  value,
  locations,
  cuisines,
  loading,
  errors,
  onChange,
  onSubmit,
}: Props) {
  const locationOptions = [
    { value: "", label: "Select a neighborhood" },
    ...locations.map((name) => ({ value: name, label: name })),
  ];
  const limitOptions = Array.from({ length: 10 }, (_, index) => {
    const n = index + 1;
    return { value: String(n), label: String(n) };
  });

  const filterCount =
    1 +
    (value.budget ? 1 : 0) +
    (value.cuisine?.trim() ? 1 : 0) +
    (value.min_rating !== "" && value.min_rating !== undefined ? 1 : 0) +
    (value.preferences?.trim() ? 1 : 0) +
    (value.limit ? 1 : 0);

  return (
    <aside className="panel search-panel">
      <div className="panel-heading">
        <div className="panel-heading-main">
          <span className="material-symbols-outlined accent-icon" aria-hidden>
            tune
          </span>
          <h2>Refine your table</h2>
        </div>
        <span className="pill">
          {filterCount} filter{filterCount === 1 ? "" : "s"}
        </span>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <CustomSelect
          id="location"
          label="Neighborhood"
          icon="location_on"
          value={value.location}
          options={locationOptions}
          placeholder="Select a neighborhood"
          searchable
          required
          error={errors.location}
          onChange={(location) => onChange({ ...value, location })}
        />

        <div className="field">
          <label htmlFor="budget">Budget</label>
          <div className="budget-grid" role="group" aria-label="Budget for two">
            {BUDGETS.map((budget) => (
              <button
                key={budget.label}
                type="button"
                className="budget-btn"
                aria-pressed={value.budget === budget.value}
                onClick={() => onChange({ ...value, budget: budget.value })}
              >
                {budget.label}
                <br />
                <span className="budget-hint">{budget.hint}</span>
              </button>
            ))}
          </div>
          {errors.budget ? <p className="field-error">{errors.budget}</p> : null}
        </div>

        <CuisineSuggest
          id="cuisine"
          value={value.cuisine || ""}
          suggestions={cuisines}
          error={errors.cuisine}
          onChange={(cuisine) => onChange({ ...value, cuisine })}
        />

        <div className="field-row">
          <div className="field">
            <label htmlFor="min-rating">Minimum rating</label>
            <div className={`control${errors.min_rating ? " is-invalid" : ""}`}>
              <input
                id="min-rating"
                type="number"
                min={0}
                max={5}
                step={0.1}
                inputMode="decimal"
                placeholder="Any"
                value={value.min_rating === "" ? "" : value.min_rating}
                onChange={(event) =>
                  onChange({
                    ...value,
                    min_rating:
                      event.target.value === ""
                        ? ""
                        : Number(event.target.value),
                  })
                }
              />
              <span
                className="material-symbols-outlined control-icon end"
                aria-hidden
              >
                star
              </span>
            </div>
            {errors.min_rating ? (
              <p className="field-error">{errors.min_rating}</p>
            ) : null}
          </div>

          <CustomSelect
            id="limit"
            label="How many"
            value={String(value.limit)}
            options={limitOptions}
            error={errors.limit}
            onChange={(limit) =>
              onChange({ ...value, limit: Number(limit) || 5 })
            }
          />
        </div>

        <div className="field">
          <label htmlFor="preferences">Extra wishes</label>
          <div className={`control textarea${errors.preferences ? " is-invalid" : ""}`}>
            <textarea
              id="preferences"
              maxLength={500}
              rows={3}
              placeholder="family-friendly, quick service…"
              value={value.preferences || ""}
              onChange={(event) =>
                onChange({ ...value, preferences: event.target.value })
              }
            />
          </div>
          <p className="hint">For example, family-friendly or quick service.</p>
          {errors.preferences ? (
            <p className="field-error">{errors.preferences}</p>
          ) : null}
        </div>

        {errors.form ? (
          <p className="field-error form-error" role="alert">
            {errors.form}
          </p>
        ) : null}

        <button className="primary-btn" type="submit" disabled={loading}>
          <span className="material-symbols-outlined filled" aria-hidden>
            auto_awesome
          </span>
          <span>{loading ? "Preparing…" : "Show recommendations"}</span>
        </button>
      </form>
    </aside>
  );
}
