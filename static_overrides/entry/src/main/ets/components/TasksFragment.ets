import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { TasksViewModel } from '../viewmodels/TasksViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';
import { Success } from '../common/Result';
import { TasksFilterType } from '../common/TasksFilterType';

/**
 * Tasks list component — embeddable in a host page.
 * Mirrors Android TasksFragment behavior: load/filter/navigate.
 */
@Component
export struct TasksFragment {
  vm: TasksViewModel = AppContainer.getTasksViewModel();
  private dao: TasksDao = new TasksDao();

  async aboutToAppear(): Promise<void> {
    await this.refresh();
  }

  async refresh(): Promise<void> {
    this.vm.dataLoading = true;
    const tasks = await this.dao.getAll();
    this.vm.filterTasks(new Success(tasks));
    this.vm.dataLoading = false;
  }

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      if (this.vm.dataLoading) {
        Column() {
          LoadingProgress().width(50).height(50)
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else if (this.vm.result.length === 0) {
        Column() {
          Text('No tasks').fontSize(16).fontColor('#999999')
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else {
        List() {
          ForEach(this.vm.result, (task: Task) => {
            ListItem() {
              Row() {
                Checkbox({ name: 'tf_cb_' + task.id })
                  .select(task.isCompleted).width(20).height(20).margin({ right: 12 })
                  .onChange((checked: boolean) => {
                    this.dao.setCompleted(task.id, checked).then(() => { this.refresh(); });
                    promptAction.showToast({
                      message: checked ? 'Task marked complete' : 'Task marked active',
                    });
                  })
                Text(task.titleForList)
                  .fontSize(16).layoutWeight(1)
                  .fontColor(task.isCompleted ? '#AAAAAA' : '#333333')
              }
              .padding({ left: 16, right: 16, top: 14, bottom: 14 })
              .width('100%').backgroundColor(Color.White)
              .onClick(() => {
                router.pushUrl({ url: 'pages/TaskDetailPage', params: { taskId: task.id } });
              })
            }
          }, (task: Task) => task.id)
        }
        .width('100%').height('100%')
        .divider({ strokeWidth: 0.5, color: '#EEEEEE', startMargin: 48 })
      }

      Button('+')
        .width(56).height(56).borderRadius(28).fontSize(28)
        .fontColor(Color.White).backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .onClick(() => { router.pushUrl({ url: 'pages/AddEditTaskPage' }); })
    }
    .width('100%').height('100%')
  }
}
