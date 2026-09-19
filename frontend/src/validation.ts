/**
 * Runtime validation schemas using Zod
 * Validates API responses at runtime to catch schema mismatches early
 */

import { z } from 'zod';

export const TaskStateEnum = z.enum(['next', 'doing', 'done', 'waiting', 'scheduled']);

export const TaskSchema = z.object({
  id: z.string().min(1, 'Task ID must not be empty'),
  agent: z.string().min(1, 'Agent must not be empty'),
  dept: z.string().min(1, 'Department must not be empty'),
  title: z.string().min(1, 'Title must not be empty'),
  state: TaskStateEnum,
  by: z.string(),
  createdAt: z.number().int().positive(),
  updatedAt: z.number().int().nonnegative(),
  model: z.string(),
  effort: z.string(),
  live: z.boolean(),
});

export const TaskListSchema = z.array(TaskSchema);

export const HealthResponseSchema = z.object({
  ok: z.boolean(),
  status: z.string(),
  version: z.string(),
  backend: z.string(),
  model: z.string(),
  brain: z.string(),
  agents: z.number().int().nonnegative(),
  notes: z.number().int().nonnegative(),
  timestamp: z.string(),
});

export const CreateTaskRequestSchema = z.object({
  department: z.string(),
  text: z.string().min(1),
  model: z.string().optional(),
  effort: z.string().optional(),
  created_by: z.string().optional(),
});

export const CreateTaskResponseSchema = z.object({
  task_id: z.string(),
  status: z.string(),
  department: z.string(),
  created_at: z.number(),
  agent: z.string().optional(),
});

export const EventMessageSchema = z.object({
  type: z.string(),
  data: z.record(z.unknown()),
  timestamp: z.string(),
});

export const TaskEventDataSchema = z.object({
  id: z.string(),
  agent: z.string(),
  dept: z.string(),
  title: z.string(),
  status: z.string(),
  created_at: z.number().optional(),
});

// Validation functions
export function validateTask(data: unknown) {
  return TaskSchema.parse(data);
}

export function validateTaskList(data: unknown) {
  return TaskListSchema.parse(data);
}

export function validateHealth(data: unknown) {
  return HealthResponseSchema.parse(data);
}

export function validateCreateTaskRequest(data: unknown) {
  return CreateTaskRequestSchema.parse(data);
}

export function validateCreateTaskResponse(data: unknown) {
  return CreateTaskResponseSchema.parse(data);
}

export function validateEventMessage(data: unknown) {
  return EventMessageSchema.parse(data);
}

// Safe validation (returns null on failure)
export function validateTaskSafe(data: unknown) {
  const result = TaskSchema.safeParse(data);
  return result.success ? result.data : null;
}

export function validateTaskListSafe(data: unknown) {
  const result = TaskListSchema.safeParse(data);
  return result.success ? result.data : null;
}

// Error reporting
export function reportValidationError(schema: string, error: z.ZodError) {
  console.error(`[Validation] ${schema} validation failed:`, {
    errors: error.errors.map(e => ({
      path: e.path.join('.'),
      message: e.message,
      code: e.code,
    })),
  });
}
