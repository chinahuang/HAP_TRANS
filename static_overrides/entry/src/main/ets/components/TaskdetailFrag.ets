import { Task } from '../common/Task';

@Component
export struct TaskdetailFrag {
  @Prop task: Task | null = null;
  @Prop dataLoading: boolean = false;
  onCompleteChange: (checked: boolean) => void = () => {};

  build() {
    if (this.dataLoading) {
      Column() {
        LoadingProgress().width(50).height(50)
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else if (this.task === null) {
      Column() {
        Text($r('app.string.no_data'))
          .fontSize(16).fontColor('#999999')
      }
      .width('100%').height('100%').justifyContent(FlexAlign.Center)
    } else {
      Column() {
        Row() {
          Checkbox({ name: 'detail_frag_cb' })
            .select(this.task!.isCompleted)
            .width(24).height(24).margin({ right: 16 })
            .onChange((checked: boolean) => { this.onCompleteChange(checked); })
          Text(this.task!.isCompleted ? 'Completed' : 'Active')
            .fontSize(14)
            .fontColor(this.task!.isCompleted ? '#4CAF50' : '#FF9800')
        }
        .width('100%').padding({ left: 16, right: 16, top: 16, bottom: 8 })

        Divider().strokeWidth(0.5).color('#EEEEEE')

        Text(this.task!.title.length > 0 ? this.task!.title : '(no title)')
          .fontSize(18).fontWeight(FontWeight.Medium)
          .fontColor(this.task!.isCompleted ? '#AAAAAA' : '#333333')
          .width('100%')
          .padding({ left: 16, right: 16, top: 16, bottom: 8 })

        Text(this.task!.description.length > 0 ? this.task!.description : '(no description)')
          .fontSize(16)
          .fontColor(this.task!.description.length > 0 ? '#555555' : '#BBBBBB')
          .width('100%')
          .padding({ left: 16, right: 16, top: 8, bottom: 16 })
      }
      .width('100%').height('100%').backgroundColor(Color.White)
    }
  }
}
