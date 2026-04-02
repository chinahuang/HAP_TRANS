// AUTO-CONVERTED: ViewModel → ArkTS @ObservedV2 class
// Dependencies injected via AppContainer (see di/AppContainer.ets)
import { TasksRepository } from '../common/TasksRepository';

@ObservedV2
export class StatisticsViewModel {
  private tasksRepository: TasksRepository;

  @Trace dataLoading: boolean = false;

  constructor(tasksRepository: TasksRepository) {
    this.tasksRepository = tasksRepository;
  }

  async refresh(): Promise<void> {
    this.dataLoading = true;
    this.tasksRepository.refreshTasks();
    this.dataLoading = false;
  }
}
