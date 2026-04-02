import { Task } from '../common/Task';
import { TasksViewModel } from '../viewmodels/TasksViewModel';

@Component
export struct TasksFrag {
  @ObjectLink vm: TasksViewModel;
  onTaskClick: (task: Task) => void = () => {};
  onAddClick: () => void = () => {};

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      if (this.vm.dataLoading) {
        Column() {
          LoadingProgress().width(50).height(50)
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else if (this.vm.result.length === 0) {
        Column() {
          if (this.vm.noTaskIconRes !== null) {
            Image(this.vm.noTaskIconRes!)
              .width(96).height(96).margin({ bottom: 16 })
          }
          if (this.vm.noTasksLabel !== null) {
            Text(this.vm.noTasksLabel!).fontSize(16).fontColor('#999999')
          }
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else {
        List() {
          ForEach(this.vm.result, (task: Task) => {
            ListItem() {
              Row() {
                Checkbox({ name: 'frag_cb_' + task.id })
                  .select(task.isCompleted)
                  .width(20).height(20).margin({ right: 12 })
                Text(task.titleForList)
                  .fontSize(16).layoutWeight(1)
                  .fontColor(task.isCompleted ? '#AAAAAA' : '#333333')
                  .decoration({
                    type: task.isCompleted
                      ? TextDecorationType.LineThrough
                      : TextDecorationType.None,
                  })
              }
              .padding({ left: 16, right: 16, top: 14, bottom: 14 })
              .width('100%').backgroundColor(Color.White)
              .onClick(() => { this.onTaskClick(task); })
            }
          }, (task: Task) => task.id)
        }
        .width('100%').height('100%')
        .divider({ strokeWidth: 0.5, color: '#EEEEEE', startMargin: 48 })
      }

      Button('+')
        .width(56).height(56).borderRadius(28)
        .fontSize(28).fontColor(Color.White).backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .onClick(() => { this.onAddClick(); })
    }
    .width('100%').height('100%')
  }
}
