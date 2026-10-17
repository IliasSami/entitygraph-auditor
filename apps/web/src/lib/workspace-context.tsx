"use client";

import * as React from "react";
import { createContext, useContext, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ProjectRead } from "@/lib/types";

interface WorkspaceContextType {
  activeProjectId: string;
  setActiveProjectId: (id: string) => void;
  activeProject: ProjectRead | null;
  projects: ProjectRead[];
  isLoading: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextType | null>(null);

const ACTIVE_PROJECT_KEY = "aentio_active_project_id";

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  // Restore the persisted workspace lazily so no state update happens in an
  // effect. An unknown/stale id simply falls through to `projects[0]` below.
  const [activeProjectId, setActiveProjectIdState] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(ACTIVE_PROJECT_KEY) ?? "";
  });

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(),
  });

  const setActiveProjectId = (id: string) => {
    setActiveProjectIdState(id);
    if (typeof window !== "undefined") {
      localStorage.setItem(ACTIVE_PROJECT_KEY, id);
    }
  };

  const activeProject =
    projects.find((p) => p.project_id === activeProjectId) ??
    projects[0] ??
    null;

  return (
    <WorkspaceContext.Provider
      value={{
        activeProjectId: activeProject ? activeProject.project_id : "",
        setActiveProjectId,
        activeProject,
        projects,
        isLoading,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return ctx;
}
