import router from '@ohos.router';
import promptAction from '@ohos.promptAction';
import { AppContainer } from '../di/AppContainer';
import { AddEditTaskViewModel } from '../viewmodels/AddEditTaskViewModel';
import { TasksDao } from '../data/TasksDao_dao';
import { Task } from '../common/Task';

@Entry
@Component
struct AddEditTaskPage {
  vm: AddEditTaskViewModel = AppContainer.getAddEditTaskViewModel();
  private dao: TasksDao = new TasksDao();
  @State pageTitle: string = 'New Task';
  @State taskId: string = '';

  async aboutToAppear(): Promise<void> {
    const params = router.getParams() as Record<string, Object>;
    this.taskId = (params?.['taskId'] ?? '') as string;
    if (this.taskId) {
      this.pageTitle = 'Edit Task';
      this.vm.isNewTask = false;
      const task = await this.dao.getById(this.taskId);
      if (task) {
        this.vm.title = task.title;
        this.vm.description = task.description;
        this.vm.taskCompleted = task.isCompleted;
      }
    } else {
      this.pageTitle = 'New Task';
      this.vm.isNewTask = true;
      this.vm.title = '';
      this.vm.description = '';
      this.vm.taskCompleted = false;
    }
  }

  private async saveAndGoBack(): Promise<void> {
    if (this.vm.title.trim().length === 0) {
      promptAction.showToast({ message: 'Title cannot be empty' });
      return;
    }
    if (this.vm.isNewTask || !this.taskId) {
      const newTask = new Task(this.vm.title, this.vm.description, false);
      await this.dao.insert(newTask);
      promptAction.showToast({ message: 'Task added' });
    } else {
      const updated = new Task(this.vm.title, this.vm.description, this.vm.taskCompleted, this.taskId);
      await this.dao.update(updated);
      promptAction.showToast({ message: 'Task saved' });
    }
    router.back();
  }

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      Column() {
        // App bar
        Row() {
          Image($r('app.media.ic_menu'))
            .width(24).height(24).fillColor(Color.White)
            .margin({ right: 8 })
            .onClick(() => { router.back(); })
          Text(this.pageTitle)
            .fontSize(20).fontWeight(FontWeight.Bold).fontColor(Color.White).layoutWeight(1)
        }
        .width('100%')
        .padding({ left: 16, right: 16, top: 48, bottom: 12 })
        .backgroundColor('#6200EE')

        if (this.vm.dataLoading) {
          Column() {
            LoadingProgress().width(50).height(50)
          }
          .width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
        } else {
          Scroll() {
            Column() {
              // Title input
              Column() {
                Text('Title')
                  .fontSize(12).fontColor('#999999').margin({ bottom: 4 })
                TextInput({ placeholder: $r('app.string.title_hint'), text: this.vm.title })
                  .fontSize(18)
                  .fontWeight(FontWeight.Medium)
                  .backgroundColor(Color.Transparent)
                  .borderRadius(0)
                  .borderWidth({ bottom: 1 })
                  .borderColor('#CCCCCC')
                  .width('100%')
                  .onChange((val: string) => { this.vm.title = val; })
              }
              .alignItems(HorizontalAlign.Start)
              .width('100%')
              .padding({ left: 16, right: 16, top: 24, bottom: 16 })

              // Description input
              Column() {
                Text('Description')
                  .fontSize(12).fontColor('#999999').margin({ bottom: 4 })
                TextArea({ placeholder: $r('app.string.description_hint'), text: this.vm.description })
                  .fontSize(16)
                  .backgroundColor(Color.Transparent)
                  .borderRadius(0)
                  .borderWidth({ bottom: 1 })
                  .borderColor('#CCCCCC')
                  .width('100%')
                  .height(150)
                  .onChange((val: string) => { this.vm.description = val; })
              }
              .alignItems(HorizontalAlign.Start)
              .width('100%')
              .padding({ left: 16, right: 16, top: 8, bottom: 16 })
            }
            .width('100%')
            .backgroundColor(Color.White)
          }
          .width('100%').layoutWeight(1)
        }
      }
      .width('100%').height('100%').backgroundColor('#F5F5F5')

      // Save FAB
      Button()
        .width(56).height(56)
        .borderRadius(28)
        .backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .backgroundImage($r('app.media.ic_done'))
        .backgroundImageSize({ width: 24, height: 24 })
        .onClick(() => { this.saveAndGoBack(); })
    }
    .width('100%').height('100%')
  }
}
