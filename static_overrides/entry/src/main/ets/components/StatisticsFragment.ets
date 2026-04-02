import { AppContainer } from '../di/AppContainer';
import { StatisticsViewModel } from '../viewmodels/StatisticsViewModel';
import { TasksDao } from '../data/TasksDao_dao';

/**
 * Statistics component — embeddable in a host page.
 * Mirrors Android StatisticsFragment behavior.
 */
@Component
export struct StatisticsFragment {
  statsVm: StatisticsViewModel = AppContainer.getStatisticsViewModel();
  private dao: TasksDao = new TasksDao();
  @State activeTasks: number = 0;
  @State completedTasks: number = 0;
  @State totalTasks: number = 0;

  async aboutToAppear(): Promise<void> {
    await this.loadStats();
  }

  private async loadStats(): Promise<void> {
    this.statsVm.dataLoading = true;
    const tasks = await this.dao.getAll();
    let active = 0;
    let completed = 0;
    for (const task of tasks) {
      task.isCompleted ? completed++ : active++;
    }
    this.activeTasks = active;
    this.completedTasks = completed;
    this.totalTasks = tasks.length;
    this.statsVm.dataLoading = false;
  }

  build() {
    if (this.statsVm.dataLoading) {
      Column() {
        LoadingProgress().width(50).height(50)
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else if (this.totalTasks === 0) {
      Column() {
        Text($r('app.string.statistics_no_tasks')).fontSize(16).fontColor('#999999')
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else {
      Column() {
        Text(`Active: ${this.activeTasks}`)
          .fontSize(16).fontColor('#333333').margin({ bottom: 8 })
        Text(`Completed: ${this.completedTasks}`)
          .fontSize(16).fontColor('#333333').margin({ bottom: 16 })
        Progress({
          value: this.completedTasks,
          total: this.totalTasks,
          type: ProgressType.Linear,
        })
          .width('100%').height(8).color('#4CAF50').backgroundColor('#EEEEEE')
      }
      .width('100%').height('100%')
      .padding({ top: 32, left: 24, right: 24 })
      .justifyContent(FlexAlign.Start)
    }
  }
}
