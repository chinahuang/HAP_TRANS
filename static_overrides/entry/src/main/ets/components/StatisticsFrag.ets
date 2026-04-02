import { StatisticsViewModel } from '../viewmodels/StatisticsViewModel';

@Component
export struct StatisticsFrag {
  @Prop activeTasks: number = 0;
  @Prop completedTasks: number = 0;
  @Prop totalTasks: number = 0;
  @Prop dataLoading: boolean = false;

  build() {
    if (this.dataLoading) {
      Column() {
        LoadingProgress().width(50).height(50)
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else if (this.totalTasks === 0) {
      Column() {
        Text($r('app.string.statistics_no_tasks'))
          .fontSize(16).fontColor('#999999')
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else {
      Column() {
        Text(`Active tasks: ${this.activeTasks}`)
          .fontSize(16).fontColor('#333333').margin({ bottom: 8 })
        Text(`Completed tasks: ${this.completedTasks}`)
          .fontSize(16).fontColor('#333333').margin({ bottom: 16 })
        Progress({
          value: this.completedTasks,
          total: this.totalTasks,
          type: ProgressType.Linear,
        })
          .width('100%').height(8)
          .color('#4CAF50').backgroundColor('#EEEEEE')
      }
      .width('100%').height('100%')
      .padding({ top: 16, bottom: 16, left: 16, right: 16 })
      .justifyContent(FlexAlign.Center)
    }
  }
}
