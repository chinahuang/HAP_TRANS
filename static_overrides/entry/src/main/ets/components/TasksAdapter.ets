import { Task } from '../common/Task';
import { TasksViewModel } from '../viewmodels/TasksViewModel';

/**
 * ArkTS equivalent of Android TasksAdapter.
 * Used by TasksFragment to render a list of tasks.
 */
export class TasksAdapter {
  private viewModel: TasksViewModel;

  constructor(viewModel: TasksViewModel) {
    this.viewModel = viewModel;
  }

  /** Returns filtered tasks from the ViewModel. */
  getTasks(): Array<Task> {
    return this.viewModel.result;
  }

  /** Determines if items are the same (by id). */
  static areItemsTheSame(oldItem: Task, newItem: Task): boolean {
    return oldItem.id === newItem.id;
  }

  /** Determines if item contents are the same. */
  static areContentsTheSame(oldItem: Task, newItem: Task): boolean {
    return oldItem.title === newItem.title &&
      oldItem.description === newItem.description &&
      oldItem.isCompleted === newItem.isCompleted;
  }
}
