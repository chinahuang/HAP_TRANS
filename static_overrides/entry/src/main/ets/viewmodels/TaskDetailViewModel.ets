// AUTO-CONVERTED: ViewModel → ArkTS @ObservedV2 class
import { TasksRepository } from '../common/TasksRepository';
import { Task } from '../common/Task';
import { Result, Success, ResultError } from '../common/Result';

@ObservedV2
export class TaskDetailViewModel {
  private tasksRepository: TasksRepository;

  @Trace taskId: string | null = null;
  @Trace task: Task | null = null;
  @Trace dataLoading: boolean = false;
  @Trace editTaskEvent: string | null = null;
  @Trace deleteTaskEvent: string | null = null;
  @Trace snackbarText: Resource | null = null;

  constructor(tasksRepository: TasksRepository) {
    this.tasksRepository = tasksRepository;
  }

  async deleteTask(): Promise<void> {
    const tid = this.taskId;
    if (tid != null) {
      this.tasksRepository.deleteTask(tid);
      this.deleteTaskEvent = 'event';
    }
  }

  async editTask(): Promise<void> {
    this.editTaskEvent = 'event';
  }

  async setCompleted(completed: boolean): Promise<void> {
    const t = this.task;
    if (t == null) return;
    if (completed) {
      this.tasksRepository.completeTask(t);
      this.showSnackbarMessage($r('app.string.task_marked_complete'));
    } else {
      this.tasksRepository.activateTask(t);
      this.showSnackbarMessage($r('app.string.task_marked_active'));
    }
  }

  async start(taskId: string | null): Promise<void> {
    if (this.dataLoading == true || (this.taskId != null && this.taskId == taskId)) {
      return;
    }
    this.taskId = taskId;
  }

  computeResult(taskResult: Result<Task>): Task | null {
    if (taskResult instanceof Success) {
      return taskResult.data;
    } else {
      this.showSnackbarMessage($r('app.string.loading_tasks_error'));
      return null;
    }
  }

  async refresh(): Promise<void> {
    const t = this.task;
    if (t != null) {
      this.dataLoading = true;
      this.tasksRepository.refreshTask(t.id);
      this.dataLoading = false;
    }
  }

  showSnackbarMessage(message: Resource): void {
    this.snackbarText = message;
  }
}
