import { Task } from './Task';
import { Result, Success, ResultError } from './Result';
import { TasksRepository } from './TasksRepository';
import { TasksDataSource } from './TasksDataSource';

/**
 * Default implementation of TasksRepository. Single entry point for managing tasks' data.
 */
export class DefaultTasksRepository implements TasksRepository {
  private tasksRemoteDataSource: TasksDataSource | null;
  private tasksLocalDataSource: TasksDataSource | null;

  constructor(tasksRemoteDataSource?: TasksDataSource, tasksLocalDataSource?: TasksDataSource) {
    this.tasksRemoteDataSource = tasksRemoteDataSource ?? null;
    this.tasksLocalDataSource = tasksLocalDataSource ?? null;
  }

  getTasks(forceUpdate: boolean): Result<Array<Task>> {
    if (forceUpdate) {
      try {
        this.updateTasksFromRemoteDataSource();
      } catch (ex) {
        return new ResultError(ex as Error);
      }
    }
    const local = this.tasksLocalDataSource;
    if (local) {
      return local.getTasks();
    }
    return new ResultError(new Error('No local data source'));
  }

  refreshTasks(): void {
    this.updateTasksFromRemoteDataSource();
  }

  observeTasks(): Promise<Result<Array<Task>>> {
    const local = this.tasksLocalDataSource;
    if (local) {
      return local.observeTasks();
    }
    return Promise.resolve(new ResultError(new Error('No local data source')));
  }

  refreshTask(taskId: string): void {
    this.updateTaskFromRemoteDataSource(taskId);
  }

  private updateTasksFromRemoteDataSource(): void {
    const remote = this.tasksRemoteDataSource;
    if (!remote) return;
    const remoteTasks: Result<Array<Task>> = remote.getTasks();
    if (remoteTasks instanceof Success) {
      const local = this.tasksLocalDataSource;
      if (local) {
        local.deleteAllTasks();
        remoteTasks.data.forEach((task: Task) => {
          local.saveTask(task);
        });
      }
    } else if (remoteTasks instanceof ResultError) {
      throw remoteTasks.exception;
    }
  }

  observeTask(taskId: string): Promise<Result<Task>> {
    const local = this.tasksLocalDataSource;
    if (local) {
      return local.observeTask(taskId);
    }
    return Promise.resolve(new ResultError(new Error('No local data source')));
  }

  private updateTaskFromRemoteDataSource(taskId: string): void {
    const remote = this.tasksRemoteDataSource;
    if (!remote) return;
    const remoteTask: Result<Task> = remote.getTask(taskId);
    if (remoteTask instanceof Success) {
      const local = this.tasksLocalDataSource;
      if (local) {
        local.saveTask(remoteTask.data);
      }
    }
  }

  getTask(taskId: string, forceUpdate: boolean): Result<Task> {
    if (forceUpdate) {
      this.updateTaskFromRemoteDataSource(taskId);
    }
    const local = this.tasksLocalDataSource;
    if (local) {
      return local.getTask(taskId);
    }
    return new ResultError(new Error('No local data source'));
  }

  saveTask(task: Task): void {
    const remote = this.tasksRemoteDataSource;
    if (remote) remote.saveTask(task);
    const local = this.tasksLocalDataSource;
    if (local) local.saveTask(task);
  }

  completeTask(taskOrId: Task | string): void {
    if (typeof taskOrId === 'string') {
      const result = this.getTaskWithId(taskOrId);
      if (result instanceof Success) {
        this.completeTask(result.data);
      }
    } else {
      const remote = this.tasksRemoteDataSource;
      if (remote) remote.completeTask(taskOrId);
      const local = this.tasksLocalDataSource;
      if (local) local.completeTask(taskOrId);
    }
  }

  activateTask(taskOrId: Task | string): void {
    if (typeof taskOrId === 'string') {
      const result = this.getTaskWithId(taskOrId);
      if (result instanceof Success) {
        this.activateTask(result.data);
      }
    } else {
      const remote = this.tasksRemoteDataSource;
      if (remote) remote.activateTask(taskOrId);
      const local = this.tasksLocalDataSource;
      if (local) local.activateTask(taskOrId);
    }
  }

  clearCompletedTasks(): void {
    const remote = this.tasksRemoteDataSource;
    if (remote) remote.clearCompletedTasks();
    const local = this.tasksLocalDataSource;
    if (local) local.clearCompletedTasks();
  }

  deleteAllTasks(): void {
    const remote = this.tasksRemoteDataSource;
    if (remote) remote.deleteAllTasks();
    const local = this.tasksLocalDataSource;
    if (local) local.deleteAllTasks();
  }

  deleteTask(taskId: string): void {
    const remote = this.tasksRemoteDataSource;
    if (remote) remote.deleteTask(taskId);
    const local = this.tasksLocalDataSource;
    if (local) local.deleteTask(taskId);
  }

  private getTaskWithId(id: string): Result<Task> {
    const local = this.tasksLocalDataSource;
    if (local) {
      return local.getTask(id);
    }
    return new ResultError(new Error('No local data source'));
  }
}
