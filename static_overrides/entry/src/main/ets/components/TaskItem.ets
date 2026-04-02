import { Task } from '../common/Task';

/**
 * Reusable task list item component.
 */
@Component
export struct TaskItem {
  @Prop task: Task = new Task();
  onCompleteChange: (task: Task, checked: boolean) => void = () => {};
  onItemClick: (task: Task) => void = () => {};

  build() {
    Row() {
      Checkbox({ name: 'item_cb_' + this.task.id })
        .select(this.task.isCompleted)
        .width(20).height(20).margin({ right: 12 })
        .onChange((checked: boolean) => { this.onCompleteChange(this.task, checked); })
      Text(this.task.titleForList)
        .fontSize(16).layoutWeight(1)
        .fontColor(this.task.isCompleted ? '#AAAAAA' : '#333333')
        .decoration({
          type: this.task.isCompleted
            ? TextDecorationType.LineThrough
            : TextDecorationType.None,
        })
    }
    .width('100%')
    .padding({ left: 16, right: 16, top: 14, bottom: 14 })
    .backgroundColor(Color.White)
    .onClick(() => { this.onItemClick(this.task); })
  }
}
