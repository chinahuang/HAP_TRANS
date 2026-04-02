import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { AddEditTaskViewModel } from '../viewmodels/AddEditTaskViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';

/**
 * Add/Edit task component — embeddable in a host page.
 * Mirrors Android AddEditTaskFragment behavior.
 */
@Component
export struct AddEditTaskFragment {
  vm: AddEditTaskViewModel = AppContainer.getAddEditTaskViewModel();
  private dao: TasksDao = new TasksDao();
  @Prop taskId: string = '';

  async aboutToAppear(): Promise<void> {
    if (this.taskId) {
      this.vm.isNewTask = false;
      const task = await this.dao.getById(this.taskId);
      if (task) {
        this.vm.title = task.title;
        this.vm.description = task.description;
        this.vm.taskCompleted = task.isCompleted;
      }
    } else {
      this.vm.isNewTask = true;
      this.vm.title = '';
      this.vm.description = '';
    }
  }

  async save(): Promise<void> {
    if (this.vm.title.trim().length === 0) {
      promptAction.showToast({ message: 'Title cannot be empty' });
      return;
    }
    if (this.vm.isNewTask || !this.taskId) {
      await this.dao.insert(new Task(this.vm.title, this.vm.description, false));
      promptAction.showToast({ message: 'Task added' });
    } else {
      await this.dao.update(new Task(this.vm.title, this.vm.description, this.vm.taskCompleted, this.taskId));
      promptAction.showToast({ message: 'Task saved' });
    }
    router.back();
  }

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      if (this.vm.dataLoading) {
        Column() {
          LoadingProgress().width(50).height(50)
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else {
        Scroll() {
          Column() {
            TextInput({ placeholder: $r('app.string.title_hint'), text: this.vm.title })
              .fontSize(18).fontWeight(FontWeight.Bold)
              .backgroundColor(Color.Transparent)
              .width('100%').margin({ bottom: 16 })
              .onChange((val: string) => { this.vm.title = val; })
            TextArea({ placeholder: $r('app.string.description_hint'), text: this.vm.description })
              .fontSize(16).backgroundColor(Color.Transparent)
              .width('100%').height(200)
              .onChange((val: string) => { this.vm.description = val; })
          }
          .width('100%').padding({ top: 24, left: 16, right: 16, bottom: 24 })
        }
        .width('100%').height('100%')
      }

      Button()
        .width(56).height(56).borderRadius(28).backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .backgroundImage($r('app.media.ic_done'))
        .backgroundImageSize({ width: 24, height: 24 })
        .onClick(() => { this.save(); })
    }
    .width('100%').height('100%')
  }
}
