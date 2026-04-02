import router from '@ohos.router';
import { AppContainer } from '../di/AppContainer';
import { StatisticsViewModel } from '../viewmodels/StatisticsViewModel';
import { TasksDao } from '../data/TasksDao_dao';

@Entry
@Component
struct StatisticsPage {
  statsVm: StatisticsViewModel = AppContainer.getStatisticsViewModel();
  private dao: TasksDao = new TasksDao();
  @State activeTasks: number = 0;
  @State completedTasks: number = 0;
  @State totalTasks: number = 0;
  @State showDrawer: boolean = false;

  async aboutToAppear(): Promise<void> {
    await this.loadStats();
  }

  async onPageShow(): Promise<void> {
    await this.loadStats();
  }

  private async loadStats(): Promise<void> {
    this.statsVm.dataLoading = true;
    const tasks = await this.dao.getAll();
    let active = 0;
    let completed = 0;
    for (const task of tasks) {
      if (task.isCompleted) {
        completed++;
      } else {
        active++;
      }
    }
    this.activeTasks = active;
    this.completedTasks = completed;
    this.totalTasks = tasks.length;
    this.statsVm.dataLoading = false;
  }

  @Builder
  DrawerContent() {
    Column() {
      // Drawer header
      Row() {
        Text('TO-DO App')
          .fontSize(18).fontWeight(FontWeight.Bold).fontColor(Color.White)
      }
      .width('100%')
      .padding({ left: 16, right: 16, top: 48, bottom: 20 })
      .backgroundColor('#6200EE')

      // Tasks item
      Row() {
        Text('Tasks')
          .fontSize(16).fontColor('#333333')
      }
      .width('100%')
      .padding({ left: 24, top: 14, bottom: 14 })
      .onClick(() => {
        this.showDrawer = false;
        router.back();
      })

      // Statistics item (current page)
      Row() {
        Text('Statistics')
          .fontSize(16).fontColor('#6200EE').fontWeight(FontWeight.Medium)
      }
      .width('100%')
      .padding({ left: 24, top: 14, bottom: 14 })
      .backgroundColor('#EDE7F6')
      .onClick(() => {
        this.showDrawer = false;
      })
    }
    .width(280)
    .height('100%')
    .backgroundColor(Color.White)
    .shadow({ radius: 8, color: '#33000000', offsetX: 2, offsetY: 0 })
  }

  build() {
    Stack() {
      Column() {
        // App bar
        Row() {
          Text('☰')
            .fontSize(22).fontColor(Color.White).margin({ right: 12 })
            .onClick(() => { this.showDrawer = true; })
          Text($r('app.string.statistics_title'))
            .fontSize(20).fontWeight(FontWeight.Bold).fontColor(Color.White).layoutWeight(1)
        }
        .width('100%')
        .padding({ left: 16, right: 16, top: 48, bottom: 12 })
        .backgroundColor('#6200EE')

        if (this.statsVm.dataLoading) {
          Column() {
            LoadingProgress().width(50).height(50)
          }
          .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else if (this.totalTasks === 0) {
          Column() {
            Image($r('app.media.ic_assignment_turned_in_24dp'))
              .width(96).height(96).margin({ bottom: 16 })
            Text($r('app.string.statistics_no_tasks'))
              .fontSize(16).fontColor('#999999')
          }
          .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else {
          Column() {
            // Stats cards
            Row() {
              Column() {
                Text(this.activeTasks.toString())
                  .fontSize(48).fontWeight(FontWeight.Bold).fontColor('#6200EE')
                Text('Active')
                  .fontSize(14).fontColor('#666666')
              }
              .layoutWeight(1)
              .padding(24)
              .backgroundColor(Color.White)
              .borderRadius(8)
              .margin({ right: 8 })

              Column() {
                Text(this.completedTasks.toString())
                  .fontSize(48).fontWeight(FontWeight.Bold).fontColor('#4CAF50')
                Text('Completed')
                  .fontSize(14).fontColor('#666666')
              }
              .layoutWeight(1)
              .padding(24)
              .backgroundColor(Color.White)
              .borderRadius(8)
              .margin({ left: 8 })
            }
            .width('100%')
            .margin({ bottom: 16 })

            // Progress card
            Column() {
              Text('Completion rate')
                .fontSize(14).fontColor('#999999').margin({ bottom: 8 })
              Text(this.totalTasks > 0
                ? Math.round(this.completedTasks * 100 / this.totalTasks).toString() + '%'
                : '0%')
                .fontSize(32).fontWeight(FontWeight.Bold).fontColor('#333333')
              Progress({
                value: this.completedTasks,
                total: this.totalTasks,
                type: ProgressType.Linear,
              })
                .width('100%').height(8)
                .color('#4CAF50')
                .backgroundColor('#EEEEEE')
                .margin({ top: 8 })
            }
            .width('100%')
            .padding(24)
            .backgroundColor(Color.White)
            .borderRadius(8)
            .alignItems(HorizontalAlign.Start)
          }
          .width('100%')
          .padding(16)
          .layoutWeight(1)
        }
      }
      .width('100%').height('100%').backgroundColor('#F5F5F5')

      // Drawer overlay
      if (this.showDrawer) {
        Column()
          .width('100%').height('100%')
          .backgroundColor('#80000000')
          .onClick(() => { this.showDrawer = false; })

        Row() {
          this.DrawerContent()
          Blank().layoutWeight(1)
        }
        .width('100%').height('100%')
      }
    }
    .width('100%').height('100%')
  }
}
