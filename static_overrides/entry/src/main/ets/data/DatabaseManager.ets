import relationalStore from '@ohos.data.relationalStore';
import common from '@ohos.app.ability.common';

const DB_NAME = 'app_database.db';

const DB_CONFIG: relationalStore.StoreConfig = {
  name: DB_NAME,
  securityLevel: relationalStore.SecurityLevel.S1,
};

const CREATE_TABLE_SQL =
  `CREATE TABLE IF NOT EXISTS tasks (
    entryid TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0
  )`;

export class DatabaseManager {
  private static instance: relationalStore.RdbStore | null = null;

  static async getInstance(context?: common.BaseContext): Promise<relationalStore.RdbStore> {
    if (!DatabaseManager.instance) {
      const ctx = context ?? getContext() as common.BaseContext;
      const rdb = await relationalStore.getRdbStore(ctx, DB_CONFIG);
      await rdb.executeSql(CREATE_TABLE_SQL, []);
      DatabaseManager.instance = rdb;
    }
    return DatabaseManager.instance!;
  }

  static async close(): Promise<void> {
    if (DatabaseManager.instance) {
      await DatabaseManager.instance.close();
      DatabaseManager.instance = null;
    }
  }
}
