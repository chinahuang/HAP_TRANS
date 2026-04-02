@Component
export struct AddtaskFrag {
  @Prop title: string = '';
  @Prop description: string = '';
  @Prop dataLoading: boolean = false;
  onTitleChange: (val: string) => void = () => {};
  onDescriptionChange: (val: string) => void = () => {};
  onSaveClick: () => void = () => {};

  build() {
    Stack({ alignContent: Alignment.BottomEnd }) {
      if (this.dataLoading) {
        Column() {
          LoadingProgress().width(50).height(50)
        }
        .width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else {
        Scroll() {
          Column() {
            TextInput({ placeholder: $r('app.string.title_hint'), text: this.title })
              .width('100%')
              .fontWeight(FontWeight.Bold)
              .backgroundColor(Color.Transparent)
              .onChange((val: string) => { this.onTitleChange(val); })
            TextInput({ placeholder: $r('app.string.description_hint'), text: this.description })
              .width('100%')
              .height(350)
              .backgroundColor(Color.Transparent)
              .onChange((val: string) => { this.onDescriptionChange(val); })
          }
          .width('100%')
          .padding({ top: 16, bottom: 16, left: 16, right: 16 })
        }
        .width('100%').height('100%')
      }

      Button()
        .width(56).height(56).borderRadius(28).backgroundColor('#6200EE')
        .margin({ right: 16, bottom: 16 })
        .backgroundImage($r('app.media.ic_done'))
        .backgroundImageSize({ width: 24, height: 24 })
        .onClick(() => { this.onSaveClick(); })
    }
    .width('100%').height('100%')
  }
}
