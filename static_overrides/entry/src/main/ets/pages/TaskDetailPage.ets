import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { TaskDetailViewModel } from '../viewmodels/TaskDetailViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';

@Entry
@Component
struct TaskDetailPage {
  detailVm: TaskDetailViewModel = AppContainer.getTaskDetailViewModel();
  private dao: TasksDao = new TasksDao();
  @State task: Task | null = null;
  @State taskId: string = '';

  async aboutToAppear(): Promise<void> {
    const params = router.getParams() as Record<string, Object>;
    this.taskId = (params?.['taskId'] ?? '') as string;
    if (this.taskId) {
      const found = await this.dao.getById(this.taskId);
      if (found) {
        this.task = found;
        this.detailVm.task = found;
      }
    }
  }

  build() {
    Column() {
      // App bar
      Row() {
        Image($r('app.media.ic_menu'))
          .width(24).height(24).fillColor(Color.White)
          .margin({ right: 8 })
          .onClick(() => { router.back(); })
        Text('Task Details')
          .fontSize(20).fontWeight(FontWeight.Bold).fontColor(Color.White).layoutWeight(1)
        Image($r('app.media.trash_icon'))
          .width(24).height(24).fillColor(Color.White)
          .onClick(() => {
            this.dao.deleteById(this.taskId).then(() => {
              promptAction.showToast({ message: 'Task deleted' });
              router.back();
            });
          })
      }
      .width('100%')
      .padding({ left: 16, right: 16, top: 48, bottom: 12 })
      .backgroundColor('#6200EE')

      if (this.task === null) {
        Column() {
          Text($r('app.string.no_data'))
            .fontSize(16).fontColor('#999999')
        }
        .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
      } else {
        // Task content
        Scroll() {
          Column() {
            // Completion checkbox row
            Row() {
              Checkbox({ name: 'detail_cb' })
                .select(this.task!.isCompleted)
                .width(24).height(24)
                .margin({ right: 16 })
                .onChange((checked: boolean) => {
                  const t = this.task!;
                  this.task = new Task(t.title, t.description, checked, t.id);
                  this.dao.setCompleted(t.id, checked);
                  promptAction.showToast({
                    message: checked ? 'Task marked complete' : 'Task marked active',
                  });
                })
              Text(this.task!.isCompleted ? 'Completed' : 'Active')
                .fontSize(14)
                .fontColor(this.task!.isCompleted ? '#4CAF50' : '#FF9800')
            }
            .width('100%')
            .padding({ left: 16, right: 16, top: 16, bottom: 8 })

            Divider().strokeWidth(0.5).color('#EEEEEE')

            // Title
            Column() {
              Text('Title')
                .fontSize(12).fontColor('#999999').margin({ bottom: 4 })
              Text(this.task!.title.length > 0 ? this.task!.title : '(no title)')
                .fontSize(18)
                .fontWeight(FontWeight.Medium)
                .fontColor(this.task!.isCompleted ? '#AAAAAA' : '#333333')
                .decoration({
                  type: this.task!.isCompleted
                    ? TextDecorationType.LineThrough
                    : TextDecorationType.None,
                })
                .width('100%')
            }
            .width('100%')
            .alignItems(HorizontalAlign.Start)
            .padding({ left: 16, right: 16, top: 16, bottom: 16 })

            Divider().strokeWidth(0.5).color('#EEEEEE')

            // Description
            Column() {
              Text('Description')
                .fontSize(12).fontColor('#999999').margin({ bottom: 4 })
              Text(this.task!.description.length > 0
                ? this.task!.description
                : '(no description)')
                .fontSize(16)
                .fontColor(this.task!.description.length > 0 ? '#555555' : '#BBBBBB')
                .width('100%')
            }
            .width('100%')
            .alignItems(HorizontalAlign.Start)
            .padding({ left: 16, right: 16, top: 16, bottom: 16 })
          }
          .width('100%')
        }
        .width('100%').layoutWeight(1)
      }
    }
    .width('100%').height('100%').backgroundColor('#F5F5F5')
    // Edit FAB via bindMenu
    .bindMenu([{
      value: 'Edit Task',
      action: () => {
        const t = this.task;
        if (t) {
          router.pushUrl({
            url: 'pages/AddEditTaskPage',
            params: { taskId: t.id },
          });
        }
      }
    }])
  }
}
