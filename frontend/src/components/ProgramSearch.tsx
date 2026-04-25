import { useState, useRef, useEffect } from "react";
import type { Program } from "../types";

interface Props {
  programs: Program[];
  value: string;
  onChange: (code: string) => void;
}

export default function ProgramSearch({ programs, value, onChange }: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = programs.find((p) => p.program_code === value);

  const filtered = query.trim()
    ? programs.filter((p) =>
        `${p.name} ${p.program_code} ${p.degree ?? ""}`.toLowerCase().includes(query.toLowerCase())
      )
    : programs;

  function pick(p: Program) {
    onChange(p.program_code);
    setQuery("");
    setOpen(false);
  }

  function clear() {
    onChange("");
    setQuery("");
    setOpen(true);
  }

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="program-search" ref={containerRef}>
      <div
        className={`program-search__input-row ${open ? "focused" : ""}`}
        onClick={() => { if (!open) setOpen(true); }}
      >
        {selected && !open ? (
          <>
            <span className="program-search__selected">
              <span className="program-search__code">{selected.program_code}</span>
              {selected.name}
              <span className="program-search__degree">{selected.degree}</span>
            </span>
            <button
              type="button"
              className="program-search__clear"
              onClick={(e) => { e.stopPropagation(); clear(); }}
              aria-label="Clear selection"
            >
              ✕
            </button>
          </>
        ) : (
          <input
            autoFocus={open}
            type="text"
            className="program-search__text"
            placeholder={selected ? `${selected.name}` : "Type to search programs…"}
            value={query}
            onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
          />
        )}
        {!selected && (
          <span className="program-search__chevron" aria-hidden>▾</span>
        )}
      </div>

      {open && (
        <ul className="program-search__dropdown" role="listbox">
          {filtered.length === 0 ? (
            <li className="program-search__empty">No programs match "{query}"</li>
          ) : (
            filtered.map((p) => (
              <li
                key={p.program_code}
                role="option"
                aria-selected={p.program_code === value}
                className={`program-search__option ${p.program_code === value ? "active" : ""}`}
                onMouseDown={(e) => { e.preventDefault(); pick(p); }}
              >
                <span className="program-search__code">{p.program_code}</span>
                <span className="program-search__label">
                  {p.name}
                  {p.degree && <span className="program-search__degree">{p.degree}</span>}
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
