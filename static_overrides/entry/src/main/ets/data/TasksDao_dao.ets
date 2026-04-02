import relationalStore from '@ohos.data.relationalStore';
import { DatabaseManager } from './DatabaseManager';
import { Task } from '../common/Task';

const TABLE = 'tasks';

function taskToRow(task: Task): relationalStore.ValuesBucket {
  const row: Record<string, relationalStore.ValueType> = {};
  row['entryid'] = task.id;
  row['title'] = task.title;
  row['description'] = task.description;
  row['completed'] = task.isCompleted ? 1 : 0;
  return row as relationalStore.ValuesBucket;
}

function rowToTask(rs: relationalStore.ResultSet): Task {
  const title = rs.getString(rs.getColumnIndex('title'));
  const description = rs.getString(rs.getColumnIndex('description'));
  const completed = rs.getLong(rs.getColumnIndex('completed'));
  const id = rs.getString(rs.getColumnIndex('entryid'));
  return new Task(title, description, completed !== 0, id);
}

export class TasksDao {
  async getAll(): Promise<Array<Task>> {
    const rdb = await DatabaseManager.getInstance();
    const rs = await rdb.querySql(`SELECT * FROM ${TABLE} ORDER BY rowid ASC`, []);
    const result: Array<Task> = [];
    while (rs.goToNextRow()) {
      result.push(rowToTask(rs));
    }
    rs.close();
    return result;
  }

  async getById(taskId: string): Promise<Task | null> {
    const rdb = await DatabaseManager.getInstance();
    const rs = await rdb.querySql(`SELECT * FROM ${TABLE} WHERE entryid = ?`, [taskId]);
    if (rs.goToNextRow()) {
      const task = rowToTask(rs);
      rs.close();
      return task;
    }
    rs.close();
    return null;
  }

  async insert(task: Task): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    await rdb.insert(TABLE, taskToRow(task));
  }

  async insertOrReplace(task: Task): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    const existing = await this.getById(task.id);
    if (existing) {
      await this.update(task);
    } else {
      await rdb.insert(TABLE, taskToRow(task));
    }
  }

  async update(task: Task): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    const predicates = new relationalStore.RdbPredicates(TABLE);
    predicates.equalTo('entryid', task.id);
    await rdb.update(taskToRow(task), predicates);
  }

  async setCompleted(taskId: string, completed: boolean): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    await rdb.executeSql(
      `UPDATE ${TABLE} SET completed = ? WHERE entryid = ?`,
      [completed ? 1 : 0, taskId]
    );
  }

  async deleteById(taskId: string): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    await rdb.executeSql(`DELETE FROM ${TABLE} WHERE entryid = ?`, [taskId]);
  }

  async deleteAll(): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    await rdb.executeSql(`DELETE FROM ${TABLE}`, []);
  }

  async deleteCompleted(): Promise<void> {
    const rdb = await DatabaseManager.getInstance();
    await rdb.executeSql(`DELETE FROM ${TABLE} WHERE completed = 1`, []);
  }
}
