import { Task } from './Task';

/*
 * Copyright (C) 2019 The Android Open Source Project
 * Licensed under the Apache License, Version 2.0
 */

/**
 * Database schema reference — converted from Android Room @Database.
 * Actual RelationalStore implementation: data/DatabaseManager.ets
 * Table schema: entryid TEXT PK, title TEXT, description TEXT, completed INTEGER
 */
export const DB_VERSION = 1;
export const DB_NAME = 'app_database.db';
