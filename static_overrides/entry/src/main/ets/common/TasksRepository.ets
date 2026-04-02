import { Task } from './Task';
import { Result } from './Result';

/*
 * Copyright (C) 2019 The Android Open Source Project
 * Licensed under the Apache License, Version 2.0
 */

/**
 * Interface to the data layer.
 * LiveData replaced with async/await + @Trace @ObservedV2 pattern.
 */
export interface TasksRepository {
  observeTasks(): Promise<Result<Array<Task>>>;
  getTasks(forceUpdate: boolean): Result<Array<Task>>;
  refreshTasks(): void;
  observeTask(taskId: string): Promise<Result<Task>>;
  getTask(taskId: string, forceUpdate: boolean): Result<Task>;
  refreshTask(taskId: string): void;
  saveTask(task: Task): void;
  completeTask(taskOrId: string | Task): void;
  activateTask(taskOrId: string | Task): void;
  clearCompletedTasks(): void;
  deleteAllTasks(): void;
  deleteTask(taskId: string): void;
}
