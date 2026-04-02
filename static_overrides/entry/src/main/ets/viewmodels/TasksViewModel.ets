// AUTO-CONVERTED: ViewModel → ArkTS @ObservedV2 class
import { TasksRepository } from '../common/TasksRepository';
import { Task } from '../common/Task';
import { Result, Success, ResultError } from '../common/Result';
import { TasksFilterType } from '../common/TasksFilterType';

const TASKS_FILTER_SAVED_STATE_KEY = 'TASKS_FILTER_SAVED_STATE_KEY';
const EDIT_RESULT_OK = 1;
const ADD_EDIT_RESULT_OK = 2;
const DELETE_RESULT_OK = 3;

@ObservedV2
export class TasksViewModel {
  private tasksRepository: TasksRepository;
  private savedStateHandle: Map<string, Object>;

  @Trace forceUpdate: boolean = false;
  @Trace dataLoading: boolean = false;
  @Trace currentFilterType: TasksFilterType = TasksFilterType.ALL_TASKS;
  @Trace currentFilteringLabel: Resource | null = null;
  @Trace noTasksLabel: Resource | null = null;
  @Trace noTaskIconRes: Resource | null = null;
  @Trace tasksAddViewVisible: boolean = false;
  @Trace snackbarText: Resource | null = null;
  @Trace openTaskEvent: string | null = null;
  @Trace newTaskEvent: string | null = null;
  @Trace isDataLoadingError: boolean = false;
  @Trace result: Array<Task> = [];
  @Trace resultMessageShown: boolean = false;

  constructor(tasksRepository: TasksRepository, savedStateHandle: Map<string, Object>) {
    this.tasksRepository = tasksRepository;
    this.savedStateHandle = savedStateHandle;
  }

  async setFiltering(requestType: TasksFilterType): Promise<void> {
    this.currentFilterType = requestType;
    this.savedStateHandle.set(TASKS_FILTER_SAVED_STATE_KEY, requestType as Object);
    switch (requestType) {
      case TasksFilterType.ALL_TASKS: {
        this.setFilter(
          $r('app.string.label_all'), $r('app.string.no_tasks_all'),
          $r('app.media.logo_no_fill'), true
        );
        break;
      }
      case TasksFilterType.ACTIVE_TASKS: {
        this.setFilter(
          $r('app.string.label_active'), $r('app.string.no_tasks_active'),
          $r('app.media.ic_check_circle_96dp'), false
        );
        break;
      }
      case TasksFilterType.COMPLETED_TASKS: {
        this.setFilter(
          $r('app.string.label_completed'), $r('app.string.no_tasks_completed'),
          $r('app.media.ic_verified_user_96dp'), false
        );
        break;
      }
    }
    this.loadTasks(false);
  }

  setFilter(
    filteringLabelString: Resource,
    noTasksLabelString: Resource,
    noTaskIconDrawable: Resource,
    tasksAddVisible: boolean
  ): void {
    this.currentFilteringLabel = filteringLabelString;
    this.noTasksLabel = noTasksLabelString;
    this.noTaskIconRes = noTaskIconDrawable;
    this.tasksAddViewVisible = tasksAddVisible;
  }

  async clearCompletedTasks(): Promise<void> {
    this.tasksRepository.clearCompletedTasks();
    this.showSnackbarMessage($r('app.string.completed_tasks_cleared'));
  }

  async completeTask(task: Task, completed: boolean): Promise<void> {
    if (completed) {
      this.tasksRepository.completeTask(task);
      this.showSnackbarMessage($r('app.string.task_marked_complete'));
    } else {
      this.tasksRepository.activateTask(task);
      this.showSnackbarMessage($r('app.string.task_marked_active'));
    }
  }

  async addNewTask(): Promise<void> {
    this.newTaskEvent = 'event';
  }

  async openTask(taskId: string): Promise<void> {
    this.openTaskEvent = taskId;
  }

  async showEditResultMessage(result: number): Promise<void> {
    if (this.resultMessageShown) return;
    switch (result) {
      case EDIT_RESULT_OK:
        this.showSnackbarMessage($r('app.string.successfully_saved_task_message'));
        break;
      case ADD_EDIT_RESULT_OK:
        this.showSnackbarMessage($r('app.string.successfully_added_task_message'));
        break;
      case DELETE_RESULT_OK:
        this.showSnackbarMessage($r('app.string.successfully_deleted_task_message'));
        break;
    }
    this.resultMessageShown = true;
  }

  showSnackbarMessage(message: Resource): void {
    this.snackbarText = message;
  }

  filterTasks(tasksResult: Result<Array<Task>>): Array<Task> {
    this.result = [];
    if (tasksResult instanceof Success) {
      this.isDataLoadingError = false;
      this.result = this.filterItems(tasksResult.data, this.getSavedFilterType());
    } else {
      this.result = [];
      this.showSnackbarMessage($r('app.string.loading_tasks_error'));
      this.isDataLoadingError = true;
    }
    return this.result;
  }

  loadTasks(forceUpdate: boolean): void {
    this.forceUpdate = forceUpdate;
  }

  filterItems(tasks: Array<Task>, filteringType: TasksFilterType): Array<Task> {
    const tasksToShow: Array<Task> = [];
    for (const task of tasks) {
      switch (filteringType) {
        case TasksFilterType.ALL_TASKS:
          tasksToShow.push(task);
          break;
        case TasksFilterType.ACTIVE_TASKS:
          if (task.isActive) { tasksToShow.push(task); }
          break;
        case TasksFilterType.COMPLETED_TASKS:
          if (task.isCompleted) { tasksToShow.push(task); }
          break;
      }
    }
    return tasksToShow;
  }

  refresh(): void {
    this.forceUpdate = true;
  }

  getSavedFilterType(): TasksFilterType {
    return (this.savedStateHandle.get(TASKS_FILTER_SAVED_STATE_KEY) as TasksFilterType) ?? TasksFilterType.ALL_TASKS;
  }
}
