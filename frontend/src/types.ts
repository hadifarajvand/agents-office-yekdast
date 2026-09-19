/**
 * Type-safe interfaces for Agent Office API responses
 * These match the backend Pydantic models
 */

export type TaskState = 'next' | 'doing' | 'done' | 'waiting' | 'scheduled';

export interface ITask {
  id: string;
  agent: string;
  dept: string;
  title: string;
  state: TaskState;
  by: string;
  createdAt: number;
  updatedAt: number;
  model: string;
  effort: string;
  live: boolean;
}

export interface IHealthResponse {
  ok: boolean;
  status: string;
  version: string;
  backend: string;
  model: string;
  brain: string;
  agents: number;
  notes: number;
  timestamp: string;
}

export interface ICreateTaskRequest {
  department: string;
  text: string;
  model?: string;
  effort?: string;
  created_by?: string;
}

export interface ICreateTaskResponse {
  task_id: string;
  status: string;
  department: string;
  created_at: number;
  agent?: string;
}

export interface IEventMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface ITaskEventData {
  id: string;
  agent: string;
  dept: string;
  title: string;
  status: string;
  created_at?: number;
}

export interface IRoutineResponse {
  id: string;
  dept: string;
  agent: string;
  title: string;
  desc: string;
  when: Record<string, unknown>;
  paused: boolean;
  nextAt: number;
  model?: string;
  effort?: string;
}

// Type guards
export function isTask(obj: unknown): obj is ITask {
  return (
    obj !== null &&
    typeof obj === 'object' &&
    'id' in obj &&
    'agent' in obj &&
    'dept' in obj &&
    'title' in obj &&
    'state' in obj &&
    'live' in obj
  );
}

export function isTaskArray(obj: unknown): obj is ITask[] {
  return Array.isArray(obj) && obj.every(isTask);
}
