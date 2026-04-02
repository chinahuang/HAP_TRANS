import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { TaskDetailViewModel } from '../viewmodels/TaskDetailViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';

/**
 * Task detail component — embeddable in a host page.
 * Mirrors Android TaskDetailFragment behavior.
 */
@Component
export struct TaskDetailFragment {
  detailVm: TaskDetailViewModel = AppContainer.getTaskDetailViewModel();
  private dao: TasksDao = new TasksDao();
  @State task: Task | null = null;
  @Prop taskId: string = '';

  async aboutToAppear(): Promise<void> {
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
      if (this.task === null) {
        Column() {
          Text($r('app.string.no_data')).fontSize(16).fontColor('#999999')
        }
        .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
      } else {
        Row() {
          Checkbox({ name: 'tdf_cb' })
            .select(this.task!.isCompleted).width(24).height(24).margin({ right: 16 })
            .onChange((checked: boolean) => {
              const t = this.task!;
              this.task = new Task(t.title, t.description, checked, t.id);
              this.dao.setCompleted(t.id, checked);
              promptAction.showToast({
                message: checked ? 'Task marked complete' : 'Task marked active',
              });
            })
          Text(this.task!.isCompleted ? 'Completed' : 'Active')
            .fontSize(14).fontColor(this.task!.isCompleted ? '#4CAF50' : '#FF9800')
        }
        .width('100%').padding({ left: 16, right: 16, top: 16, bottom: 8 })

        Divider().strokeWidth(0.5).color('#EEEEEE')

        Text(this.task!.title.length > 0 ? this.task!.title : '(no title)')
          .fontSize(18).fontWeight(FontWeight.Medium)
          .fontColor(this.task!.isCompleted ? '#AAAAAA' : '#333333')
          .width('100%').padding({ left: 16, right: 16, top: 16, bottom: 8 })

        Text(this.task!.description.length > 0 ? this.task!.description : '(no description)')
          .fontSize(16)
          .fontColor(this.task!.description.length > 0 ? '#555555' : '#BBBBBB')
          .width('100%').padding({ left: 16, right: 16, top: 8, bottom: 16 })
      }
    }
    .width('100%').height('100%').backgroundColor(Color.White)
  }
}
