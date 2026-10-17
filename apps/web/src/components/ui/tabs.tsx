"use client";

import * as React from "react";
import { cn } from "@/lib/format";

interface TabsContextValue {
  value: string;
  setValue: (value: string) => void;
  idBase: string;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabs(): TabsContextValue {
  const context = React.useContext(TabsContext);
  if (!context) throw new Error("Tabs components must be used inside <Tabs>");
  return context;
}

export interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
  /** Accessible name for the tablist. */
  label?: string;
}

export function Tabs({ value, onValueChange, children, className, label }: TabsProps) {
  const idBase = React.useId();
  return (
    <TabsContext.Provider value={{ value, setValue: onValueChange, idBase }}>
      <div className={className} data-tabs-root="">
        {React.Children.map(children, (child) =>
          React.isValidElement(child) && label && child.type === TabsList
            ? React.cloneElement(child as React.ReactElement<{ "aria-label"?: string }>, {
                "aria-label": label,
              })
            : child,
        )}
      </div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const { value, setValue } = useTabs();

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const list = event.currentTarget;
    const triggers = Array.from(list.querySelectorAll<HTMLElement>('[role="tab"]:not([disabled])'));
    const index = triggers.findIndex((trigger) => trigger.dataset.value === value);
    if (index === -1) return;
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % triggers.length;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + triggers.length) % triggers.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = triggers.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = triggers[nextIndex];
    next.focus();
    setValue(next.dataset.value ?? value);
  };

  return (
    <div
      role="tablist"
      onKeyDown={onKeyDown}
      className={cn(
        "inline-flex flex-wrap items-center gap-1 rounded-md bg-muted p-1",
        className,
      )}
      {...props}
    />
  );
}

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({ value, className, children, ...props }: TabsTriggerProps) {
  const { value: active, setValue, idBase } = useTabs();
  const selected = active === value;
  return (
    <button
      type="button"
      role="tab"
      id={`${idBase}-tab-${value}`}
      aria-selected={selected}
      aria-controls={`${idBase}-panel-${value}`}
      tabIndex={selected ? 0 : -1}
      data-value={value}
      onClick={() => setValue(value)}
      className={cn(
        "rounded px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline-2 focus-visible:outline-ring",
        selected ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export function TabsContent({ value, className, children, ...props }: TabsContentProps) {
  const { value: active, idBase } = useTabs();
  if (active !== value) return null;
  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${value}`}
      aria-labelledby={`${idBase}-tab-${value}`}
      tabIndex={0}
      className={cn("mt-4 focus-visible:outline-2 focus-visible:outline-ring", className)}
      {...props}
    >
      {children}
    </div>
  );
}
