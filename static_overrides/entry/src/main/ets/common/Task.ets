// AUTO-CONVERTED from Android: C:\work\android_sample\app\src\main\java\com\example\android\architecture\blueprints\todoapp\data\Task.kt
// Target: ArkTS
// WARNING: This file requires manual review.
// Search for TODO comments to find unconverted sections.

/*
 * Copyright (C) 2019 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Immutable model class for a Task.
 */
export class Task {
  readonly title: string;
  readonly description: string;
  readonly isCompleted: boolean;
  readonly id: string;

  constructor(
    title: string = '',
    description: string = '',
    isCompleted: boolean = false,
    id: string = Math.random().toString(36).substring(2)
  ) {
    this.title = title;
    this.description = description;
    this.isCompleted = isCompleted;
    this.id = id;
  }

  get titleForList(): string {
    return (this.title.length > 0 ? this.title : this.description);
  }

  get isActive(): boolean {
    return !this.isCompleted;
  }

  get isEmpty(): boolean {
    return this.title.length === 0 && this.description.length === 0;
  }
}
