import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { TasksViewModel } from '../viewmodels/TasksViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';
import { Success } from '../common/Result';
import { TasksFilterType } from '../common/TasksFilterType';

@Entry
@Component
struct TasksPage {
  vm: TasksViewModel = AppContainer.getTasksViewModel();
  private dao: TasksDao = new TasksDao();
  @State showDrawer: boolean = false;

  async aboutToAppear(): Promise<void> {
    await this.loadTasks();
  }

  async onPageShow(): Promise<void> {
    await this.loadTasks();
  }

  private async loadTasks(): Promise<void> {
    this.vm.dataLoading = true;
    const tasks = await this.dao.getAll();
    this.vm.filterTasks(new Success(tasks));
    this.vm.dataLoading = false;
  }

  private applyFilter(type: TasksFilterType): void {
    this.vm.setFiltering(type);
    this.loadTasks();
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

      // Tasks item (current page)
      Row() {
        Text('Tasks')
          .fontSize(16).fontColor('#6200EE').fontWeight(FontWeight.Medium)
      }
      .width('100%')
      .padding({ left: 24, top: 14, bottom: 14 })
      .backgroundColor('#EDE7F6')
      .onClick(() => {
        this.showDrawer = false;
      })

      // Statistics item
      Row() {
        Text('Statistics')
          .fontSize(16).fontColor('#333333')
      }
      .width('100%')
      .padding({ left: 24, top: 14, bottom: 14 })
      .onClick(() => {
        this.showDrawer = false;
        router.pushUrl({ url: 'pages/StatisticsPage' });
      })
    }
    .width(280)
    .height('100%')
    .backgroundColor(Color.White)
    .shadow({ radius: 8, color: '#33000000', offsetX: 2, offsetY: 0 })
  }

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      Column() {
        // App bar
        Row() {
          // Hamburger
          Text('☰')
            .fontSize(22).fontColor(Color.White).margin({ right: 12 })
            .onClick(() => { this.showDrawer = true; })
          Text($r('app.string.app_name'))
            .fontSize(20).fontWeight(FontWeight.Bold).fontColor(Color.White).layoutWeight(1)
          // Overflow menu
          Text('⋮')
            .fontSize(24).fontColor(Color.White).padding({ left: 8, right: 4 })
            .bindMenu([
              {
                value: 'Clear completed',
                action: () => {
                  this.dao.deleteCompleted().then(() => {
                    this.loadTasks();
                  });
                }
              },
              {
                value: 'Refresh',
                action: () => { this.loadTasks(); }
              }
            ])
        }
        .width('100%')
        .padding({ left: 16, right: 16, top: 48, bottom: 12 })
        .backgroundColor('#6200EE')

        // Filter tabs
        Row() {
          Button('All')
            .layoutWeight(1).height(36)
            .type(ButtonType.Normal).borderRadius(0)
            .fontSize(13)
            .backgroundColor(
              this.vm.currentFilterType === TasksFilterType.ALL_TASKS ? '#EDE7F6' : Color.White
            )
            .fontColor(
              this.vm.currentFilterType === TasksFilterType.ALL_TASKS ? '#6200EE' : '#666666'
            )
            .onClick(() => { this.applyFilter(TasksFilterType.ALL_TASKS); })
          Button('Active')
            .layoutWeight(1).height(36)
            .type(ButtonType.Normal).borderRadius(0)
            .fontSize(13)
            .backgroundColor(
              this.vm.currentFilterType === TasksFilterType.ACTIVE_TASKS ? '#EDE7F6' : Color.White
            )
            .fontColor(
              this.vm.currentFilterType === TasksFilterType.ACTIVE_TASKS ? '#6200EE' : '#666666'
            )
            .onClick(() => { this.applyFilter(TasksFilterType.ACTIVE_TASKS); })
          Button('Completed')
            .layoutWeight(1).height(36)
            .type(ButtonType.Normal).borderRadius(0)
            .fontSize(13)
            .backgroundColor(
              this.vm.currentFilterType === TasksFilterType.COMPLETED_TASKS ? '#EDE7F6' : Color.White
            )
            .fontColor(
              this.vm.currentFilterType === TasksFilterType.COMPLETED_TASKS ? '#6200EE' : '#666666'
            )
            .onClick(() => { this.applyFilter(TasksFilterType.COMPLETED_TASKS); })
        }
        .width('100%')
        .backgroundColor(Color.White)

        // Content area
        if (this.vm.dataLoading) {
          Column() {
            LoadingProgress().width(50).height(50)
          }
          .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else if (this.vm.result.length === 0) {
          Column() {
            Image($r('app.media.logo_no_fill'))
              .width(96).height(96).margin({ bottom: 16 })
            Text('No tasks')
              .fontSize(16).fontColor('#999999')
          }
          .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else {
          List() {
            ForEach(this.vm.result, (task: Task) => {
              ListItem() {
                Row() {
                  Checkbox({ name: 'cb_' + task.id })
                    .select(task.isCompleted)
                    .width(20).height(20)
                    .margin({ right: 12 })
                    .onChange((checked: boolean) => {
                      this.dao.setCompleted(task.id, checked).then(() => {
                        this.loadTasks();
                      });
                      promptAction.showToast({
                        message: checked ? 'Task marked complete' : 'Task marked active',
                      });
                    })
                  Text(task.titleForList)
                    .fontSize(16)
                    .layoutWeight(1)
                    .fontColor(task.isCompleted ? '#AAAAAA' : '#333333')
                    .decoration({
                      type: task.isCompleted
                        ? TextDecorationType.LineThrough
                        : TextDecorationType.None,
                    })
                }
                .padding({ left: 16, right: 16, top: 14, bottom: 14 })
                .width('100%')
                .backgroundColor(Color.White)
                .onClick(() => {
                  router.pushUrl({
                    url: 'pages/TaskDetailPage',
                    params: { taskId: task.id },
                  });
                })
              }
            }, (task: Task) => task.id)
          }
          .width('100%')
          .layoutWeight(1)
          .divider({ strokeWidth: 0.5, color: '#EEEEEE', startMargin: 48 })
          .backgroundColor('#F5F5F5')
        }
      }
      .width('100%').height('100%')

      // FAB
      Button('+')
        .width(56).height(56)
        .borderRadius(28)
        .fontSize(28)
        .fontColor(Color.White)
        .backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .onClick(() => {
          router.pushUrl({ url: 'pages/AddEditTaskPage' });
        })

      // Drawer overlay
      if (this.showDrawer) {
        // Scrim
        Column()
          .width('100%').height('100%')
          .backgroundColor('#80000000')
          .onClick(() => { this.showDrawer = false; })

        // Drawer panel (left-aligned inside Stack)
        Row() {
          this.DrawerContent()
          Blank().layoutWeight(1)
        }
        .width('100%').height('100%')
      }
    }
    .width('100%').height('100%')
    .backgroundColor('#F5F5F5')
  }
}
