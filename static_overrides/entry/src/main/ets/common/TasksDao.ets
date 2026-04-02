import { Task } from './Task';

/*
 * Copyright (C) 2019 The Android Open Source Project
 * Licensed under the Apache License, Version 2.0
 */

/**
 * DAO interface for the tasks table.
 * Converted from Android Room @Dao — implementation in data/TasksDao_dao.ets.
 */
export interface TasksDao {
  observeTasks(): Promise<Array<Task>>;
  observeTaskById(taskId: string): Promise<Task | null>;
  getTasks(): Promise<Array<Task>>;
  getTaskById(taskId: string): Promise<Task | null>;
  insertTask(task: Task): Promise<void>;
  updateTask(task: Task): Promise<void>;
  updateCompleted(taskId: string, completed: boolean): Promise<void>;
  deleteTaskById(taskId: string): Promise<void>;
  deleteTasks(): Promise<void>;
  deleteCompletedTasks(): Promise<void>;
}
