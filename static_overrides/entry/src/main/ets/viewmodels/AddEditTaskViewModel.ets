// AUTO-CONVERTED: ViewModel → ArkTS @ObservedV2 class
import { TasksRepository } from '../common/TasksRepository';
import { Task } from '../common/Task';
import { Result, Success, ResultError } from '../common/Result';

@ObservedV2
export class AddEditTaskViewModel {
  private tasksRepository: TasksRepository;

  @Trace dataLoading: boolean = false;
  @Trace snackbarText: Resource | null = null;
  @Trace taskUpdatedEvent: string | null = null;
  @Trace title: string = '';
  @Trace description: string = '';
  @Trace taskId: string | null = null;
  @Trace isNewTask: boolean = false;
  @Trace isDataLoaded: boolean = false;
  @Trace taskCompleted: boolean = false;

  constructor(tasksRepository: TasksRepository) {
    this.tasksRepository = tasksRepository;
  }

  async start(taskId: string | null): Promise<void> {
    if (this.dataLoading == true) {
      return;
    }
    this.taskId = taskId;
    if (this.taskId == null) {
      this.isNewTask = true;
      return;
    }
    if (this.isDataLoaded) {
      return;
    }
    this.isNewTask = false;
    this.dataLoading = true;
    const taskResult = this.tasksRepository.getTask(this.taskId, false);
    if (taskResult instanceof Success) {
      await this.onTaskLoaded(taskResult.data);
    } else {
      await this.onDataNotAvailable();
    }
  }

  async onTaskLoaded(task: Task): Promise<void> {
    this.title = task.title;
    this.description = task.description;
    this.taskCompleted = task.isCompleted;
    this.dataLoading = false;
    this.isDataLoaded = true;
  }

  async onDataNotAvailable(): Promise<void> {
    this.dataLoading = false;
  }

  async saveTask(): Promise<void> {
    const currentTitle = this.title;
    const currentDescription = this.description;
    if (new Task(currentTitle, currentDescription).isEmpty) {
      this.snackbarText = $r('app.string.empty_task_message');
      return;
    }
    const currentTaskId = this.taskId;
    if (this.isNewTask || currentTaskId == null) {
      await this.createTask(new Task(currentTitle, currentDescription));
    } else {
      const task = new Task(currentTitle, currentDescription, this.taskCompleted, currentTaskId);
      await this.updateTask(task);
    }
  }

  async createTask(newTask: Task): Promise<void> {
    this.tasksRepository.saveTask(newTask);
    this.taskUpdatedEvent = 'event';
  }

  async updateTask(task: Task): Promise<void> {
    if (this.isNewTask) {
      throw new Error('updateTask() was called but task is new.');
    }
    this.tasksRepository.saveTask(task);
    this.taskUpdatedEvent = 'event';
  }
}
