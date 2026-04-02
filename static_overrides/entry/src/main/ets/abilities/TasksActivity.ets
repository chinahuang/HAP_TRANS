// UIAbility entry point for the TO-DO app.
// Navigation drawer is implemented in TasksPage.ets via @State showDrawer + Stack overlay.

import UIAbility from '@ohos.app.ability.UIAbility';
import window from '@ohos.window';
import Want from '@ohos.app.ability.Want';
import AbilityConstant from '@ohos.app.ability.AbilityConstant';

export default class TasksActivity extends UIAbility {

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    console.info('TasksActivity onCreate');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/TasksPage', (err) => {
      if (err.code !== 0) {
        console.error('TasksActivity loadContent error:', JSON.stringify(err));
      }
    });
  }

  onForeground(): void {
    console.info('TasksActivity onForeground');
  }

  onBackground(): void {
    console.info('TasksActivity onBackground');
  }

  onDestroy(): void {
    console.info('TasksActivity onDestroy');
  }
}
